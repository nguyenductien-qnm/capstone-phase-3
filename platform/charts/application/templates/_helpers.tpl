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
app.kubernetes.io/part-of: techx-corp
app.kubernetes.io/managed-by: {{ .Release.Service }}
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

{{/*
Validate that an image string is pinned (has a tag that is not :latest).
Usage: include "techx-corp.validateNoLatest" (list "image-string" "context-name")
Fails helm template if any image uses :latest or has no tag.
*/}}
{{- define "techx-corp.validateNoLatest" -}}
{{- $image := index . 0 -}}
{{- $context := index . 1 -}}
{{- if not $image -}}
  {{- fail (printf "VALIDATION FAIL: %s has an empty image reference" $context) -}}
{{- end -}}

{{- if hasSuffix ":latest" $image -}}
  {{- fail (printf "VALIDATION FAIL: %s uses :latest tag: %s" $context $image) -}}
{{- end -}}

{{- if not (contains ":" $image) -}}
  {{- fail (printf "VALIDATION FAIL: %s has no tag (defaults to :latest): %s" $context $image) -}}
{{- end -}}
{{- end -}}

{{/* Return an image reference without appending a tag to a digest. */}}
{{- define "techx-corp.imageReference" -}}
{{- $image := index . 0 -}}
{{- $context := index . 1 -}}
{{- $repository := $image.repository -}}
{{- $digest := $image.digest | default "" -}}
{{- $tag := $image.tag | default "" -}}
{{- if $digest -}}
{{- if not (regexMatch "^sha256:[a-f0-9]{64}$" $digest) -}}
{{- fail (printf "VALIDATION FAIL: %s digest must match sha256:<64 lowercase hex> (got %s)" $context $digest) -}}
{{- end -}}
{{- printf "%s@%s" $repository $digest -}}
{{- else -}}
{{- printf "%s:%s" $repository ($tag | default "latest") -}}
{{- end -}}
{{- end -}}
