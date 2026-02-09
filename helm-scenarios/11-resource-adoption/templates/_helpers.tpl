{{/*
Generate the full name for resources.
Must match the existing resource names exactly for adoption to work.
*/}}
{{- define "adopted-app.fullname" -}}
adopted-app
{{- end -}}

{{/*
Common labels applied to all resources.
*/}}
{{- define "adopted-app.labels" -}}
app: adopted-app
app.kubernetes.io/name: adopted-app
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.appVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- end -}}

{{/*
Selector labels -- must match the existing deployment's matchLabels exactly.
*/}}
{{- define "adopted-app.selectorLabels" -}}
app: adopted-app
{{- end -}}
