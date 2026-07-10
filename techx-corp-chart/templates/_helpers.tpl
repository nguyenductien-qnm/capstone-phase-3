{{/*
Expand the name of the chart.
*/}}
{{- define "techx-corp.name" -}}
{{- default .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "techx-corp.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "techx-corp.labels" -}}
helm.sh/chart: {{ include "techx-corp.chart" . }}
{{ include "techx-corp.selectorLabels" . }}
{{ include "techx-corp.workloadLabels" . }}
{{ include "techx-corp.finopsLabels" . }}
app.kubernetes.io/part-of: techx-corp
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
FinOps labels for ownership, traceability, and cost allocation.
*/}}
{{- define "techx-corp.finopsLabels" -}}
{{- $global := .Values.global | default dict }}
{{- $finops := $global.finops | default dict }}
{{- $labels := $finops.labels | default dict }}
{{- range $key, $value := $labels }}
{{ $key }}: {{ $value | quote }}
{{- end }}
techx.io/service: {{ default "platform" .name | quote }}
{{- end }}



{{/*
Workload (Pod) labels
*/}}
{{- define "techx-corp.workloadLabels" -}}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
{{- if .name }}
app.kubernetes.io/component: {{ .name}}
app.kubernetes.io/name: {{ .name }}
{{- end }}
{{- end }}




{{/*
Selector labels
*/}}
{{- define "techx-corp.selectorLabels" -}}
{{- if .name }}
opentelemetry.io/name: {{ .name }}
{{- end }}
{{- end }}

{{- define "techx-corp.envOverriden" -}}
{{- $mergedEnvs := list }}
{{- $envOverrides := default (list) .envOverrides }}

{{- range .env }}
{{-   $currentEnv := . }}
{{-   $hasOverride := false }}
{{-   range $envOverrides }}
{{-     if eq $currentEnv.name .name }}
{{-       $mergedEnvs = append $mergedEnvs . }}
{{-       $envOverrides = without $envOverrides . }}
{{-       $hasOverride = true }}
{{-     end }}
{{-   end }}
{{-   if not $hasOverride }}
{{-     $mergedEnvs = append $mergedEnvs $currentEnv }}
{{-   end }}
{{- end }}
{{- $mergedEnvs = concat $mergedEnvs $envOverrides }}
{{- mustToJson $mergedEnvs }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "techx-corp.serviceAccountName" -}}
{{- if .serviceAccount.create }}
{{- default (include "techx-corp.name" .) .serviceAccount.name }}
{{- else }}
{{- default "default" .serviceAccount.name }}
{{- end }}
{{- end }}
