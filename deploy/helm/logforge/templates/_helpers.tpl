{{- define "logforge.name" -}}{{ .Chart.Name }}{{- end -}}
{{- define "logforge.fullname" -}}{{ printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}{{- end -}}
{{- define "logforge.labels" -}}
app.kubernetes.io/name: {{ include "logforge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}
{{- define "logforge.selector" -}}
app.kubernetes.io/name: {{ include "logforge.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}
{{- define "logforge.secretName" -}}{{ .Values.secrets.existingSecret | default (printf "%s-secrets" (include "logforge.fullname" .)) }}{{- end -}}
{{- define "logforge.image" -}}{{ .image.repository }}:{{ .image.tag | default .root.Chart.AppVersion }}{{- end -}}
{{/* Environment shared by the API and its jobs. */}}
{{- define "logforge.apiEnv" -}}
- name: CLICKHOUSE_PASSWORD
  valueFrom: {secretKeyRef: {name: {{ include "logforge.secretName" . }}, key: clickhouse-password}}
- name: JWT_SECRET
  valueFrom: {secretKeyRef: {name: {{ include "logforge.secretName" . }}, key: jwt-secret}}
- name: LOGFORGE_S3_ACCESS_KEY
  valueFrom: {secretKeyRef: {name: {{ include "logforge.secretName" . }}, key: s3-access-key}}
- name: LOGFORGE_S3_SECRET_KEY
  valueFrom: {secretKeyRef: {name: {{ include "logforge.secretName" . }}, key: s3-secret-key}}
{{- end -}}
