-- Lua script for transforming logs to Logforge format

function transform_for_logforge(tag, timestamp, record)
    -- Create new record with Logforge-required fields
    local new_record = {}
    
    -- Set timestamp (required)
    new_record["timestamp"] = os.date("!%Y-%m-%dT%H:%M:%S.000Z", timestamp)
    
    -- Map common fields to Logforge format
    -- message -> msg (required)
    new_record["msg"] = record["message"] or record["log"] or record["msg"] or ""
    
    -- Set level (default to info if not provided)
    local level = record["level"] or record["severity"] or "info"
    level = string.lower(level)
    
    -- Map log levels to Logforge standard levels
    if level == "warning" or level == "warn" then
        new_record["level"] = "warn"
    elseif level == "err" or level == "error" then
        new_record["level"] = "error"
    elseif level == "debug" or level == "trace" then
        new_record["level"] = "debug"
    else
        new_record["level"] = "info"
    end
    
    -- Set host (use existing or from environment)
    new_record["host"] = record["host"] or record["hostname"] or os.getenv("HOSTNAME") or "unknown"
    
    -- Set service (extract from various fields)
    new_record["service"] = record["service"] or 
                           record["app"] or 
                           record["application"] or 
                           record["container_name"] or
                           "fluent-bit"
    
    -- Set user_id if available
    if record["user_id"] or record["userId"] or record["user"] then
        new_record["user_id"] = record["user_id"] or record["userId"] or record["user"]
    end
    
    -- Set trace_id if available
    if record["trace_id"] or record["traceId"] or record["trace"] then
        new_record["trace_id"] = record["trace_id"] or record["traceId"] or record["trace"]
    end
    
    -- Set span_id if available
    if record["span_id"] or record["spanId"] or record["span"] then
        new_record["span_id"] = record["span_id"] or record["spanId"] or record["span"]
    end
    
    -- Set src_ip if available
    if record["src_ip"] or record["remote_addr"] or record["client_ip"] then
        new_record["src_ip"] = record["src_ip"] or record["remote_addr"] or record["client_ip"]
    end
    
    -- Set status if available
    if record["status"] or record["http_status"] or record["status_code"] then
        local status = record["status"] or record["http_status"] or record["status_code"]
        new_record["status"] = tonumber(status) or 0
    end
    
    -- Pack remaining fields into attrs
    new_record["attrs"] = {}
    
    for key, value in pairs(record) do
        -- Skip fields we've already mapped
        if key ~= "message" and key ~= "log" and key ~= "msg" and
           key ~= "level" and key ~= "severity" and 
           key ~= "host" and key ~= "hostname" and
           key ~= "service" and key ~= "app" and key ~= "application" and
           key ~= "container_name" and
           key ~= "user_id" and key ~= "userId" and key ~= "user" and
           key ~= "trace_id" and key ~= "traceId" and key ~= "trace" and
           key ~= "span_id" and key ~= "spanId" and key ~= "span" and
           key ~= "src_ip" and key ~= "remote_addr" and key ~= "client_ip" and
           key ~= "status" and key ~= "http_status" and key ~= "status_code" then
            new_record["attrs"][key] = value
        end
    end
    
    -- Add Fluent Bit specific metadata
    new_record["attrs"]["fluent_bit_tag"] = tag
    new_record["attrs"]["fluent_bit_timestamp"] = timestamp
    
    return 1, timestamp, new_record
end

-- Alternative function for nginx-specific transformation
function transform_nginx_for_logforge(tag, timestamp, record)
    local new_record = {}
    
    -- For nginx access logs, preserve original format for dedicated endpoint
    if record["remote_addr"] and record["method"] and record["path"] then
        -- This is likely an nginx access log
        new_record["log_line"] = record["message"] or record["log"] or ""
        new_record["timestamp"] = os.date("!%Y-%m-%dT%H:%M:%S.000Z", timestamp)
        new_record["host"] = record["host"] or os.getenv("HOSTNAME") or "unknown"
        new_record["service"] = "nginx"
        new_record["log_type"] = "access"
        
        -- Add parsed fields to attrs
        new_record["attrs"] = {
            remote_addr = record["remote_addr"],
            method = record["method"],
            path = record["path"],
            status = record["status"],
            bytes_sent = record["bytes_sent"],
            http_user_agent = record["http_user_agent"],
            http_referer = record["http_referer"]
        }
        
        return 1, timestamp, new_record
    else
        -- Fall back to standard transformation
        return transform_for_logforge(tag, timestamp, record)
    end
end