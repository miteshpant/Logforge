-- Kubernetes-specific transformation for Logforge

function transform_kubernetes_for_logforge(tag, timestamp, record)
    local new_record = {}
    
    -- Set timestamp
    new_record["timestamp"] = os.date("!%Y-%m-%dT%H:%M:%S.000Z", timestamp)
    
    -- Set message (required field)
    new_record["msg"] = record["msg"] or record["log"] or record["message"] or ""
    
    -- Extract Kubernetes metadata
    local kubernetes = record["kubernetes"] or {}
    
    -- Set host from node name
    new_record["host"] = kubernetes["host"] or 
                        kubernetes["node_name"] or 
                        record["host"] or 
                        os.getenv("NODE_NAME") or 
                        "kubernetes-node"
    
    -- Set service from Kubernetes labels/metadata
    local service = kubernetes["container_name"] or "kubernetes"
    
    if kubernetes["labels"] then
        -- Prefer standard app labels
        service = kubernetes["labels"]["app.kubernetes.io/name"] or
                 kubernetes["labels"]["app"] or
                 kubernetes["labels"]["k8s-app"] or
                 service
    end
    
    new_record["service"] = service
    
    -- Set log level based on stream and content
    local level = "info"
    if record["stream"] == "stderr" then
        level = "error"
    else
        -- Try to detect level from message content
        local msg_lower = string.lower(new_record["msg"])
        if string.match(msg_lower, "error") or string.match(msg_lower, "err:") then
            level = "error"
        elseif string.match(msg_lower, "warn") or string.match(msg_lower, "warning") then
            level = "warn"
        elseif string.match(msg_lower, "debug") or string.match(msg_lower, "trace") then
            level = "debug"
        end
    end
    new_record["level"] = level
    
    -- Extract trace information if available in message
    local trace_match = string.match(new_record["msg"], "trace[_-]?id[=:]?%s*([%w%-]+)")
    if trace_match then
        new_record["trace_id"] = trace_match
    end
    
    local span_match = string.match(new_record["msg"], "span[_-]?id[=:]?%s*([%w%-]+)")
    if span_match then
        new_record["span_id"] = span_match
    end
    
    -- Build attrs with Kubernetes metadata
    new_record["attrs"] = {
        -- Kubernetes core metadata
        ["kubernetes.namespace"] = kubernetes["namespace_name"],
        ["kubernetes.pod_name"] = kubernetes["pod_name"],
        ["kubernetes.container_name"] = kubernetes["container_name"],
        ["kubernetes.pod_id"] = kubernetes["pod_id"],
        ["kubernetes.docker_id"] = kubernetes["docker_id"],
        ["stream"] = record["stream"],
        
        -- Fluent Bit metadata
        ["fluent_bit.tag"] = tag,
        ["fluent_bit.source"] = "kubernetes"
    }
    
    -- Add pod labels as attributes
    if kubernetes["labels"] then
        for key, value in pairs(kubernetes["labels"]) do
            new_record["attrs"]["kubernetes.labels." .. key] = value
        end
    end
    
    -- Add pod annotations as attributes (limited to useful ones)
    if kubernetes["annotations"] then
        local useful_annotations = {
            "prometheus.io/scrape",
            "prometheus.io/port", 
            "prometheus.io/path",
            "fluentbit.io/parser",
            "fluentbit.io/exclude"
        }
        
        for _, annotation in ipairs(useful_annotations) do
            if kubernetes["annotations"][annotation] then
                local safe_key = string.gsub(annotation, "[%./]", "_")
                new_record["attrs"]["kubernetes.annotations." .. safe_key] = kubernetes["annotations"][annotation]
            end
        end
    end
    
    -- Add any additional fields from the original record
    for key, value in pairs(record) do
        if key ~= "msg" and key ~= "log" and key ~= "message" and
           key ~= "kubernetes" and key ~= "stream" and key ~= "time" and
           key ~= "@timestamp" then
            new_record["attrs"][key] = value
        end
    end
    
    return 1, timestamp, new_record
end

-- Function to check if this is an nginx access log
function is_nginx_access_log(msg)
    -- Basic pattern matching for nginx access log format
    return string.match(msg, '^%d+%.%d+%.%d+%.%d+') and 
           string.match(msg, '%[%d+/%a+/%d+:')
end

-- Function to check if this is a syslog message
function is_syslog_message(msg)
    -- Basic pattern for RFC3164 syslog format
    return string.match(msg, '^<%d+>')
end

-- Routing function to determine output endpoint
function route_kubernetes_logs(tag, timestamp, record)
    local msg = record["msg"] or record["log"] or record["message"] or ""
    
    -- Determine routing based on message format
    if is_nginx_access_log(msg) then
        -- Route to nginx endpoint
        return 1, timestamp, {
            ["log_line"] = msg,
            ["timestamp"] = os.date("!%Y-%m-%dT%H:%M:%S.000Z", timestamp),
            ["host"] = (record["kubernetes"] or {})["host"] or "kubernetes-node",
            ["service"] = "nginx",
            ["attrs"] = record["kubernetes"] or {}
        }
    elseif is_syslog_message(msg) then
        -- Route to syslog endpoint - just pass the raw message
        return 1, timestamp, { ["syslog_message"] = msg }
    else
        -- Default JSON routing
        return transform_kubernetes_for_logforge(tag, timestamp, record)
    end
end