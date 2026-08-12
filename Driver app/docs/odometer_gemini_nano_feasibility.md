# Gemini Nano odometer feasibility decision

Decision date: 2026-08-11  
Decision: **NO-SHIP; retain deterministic ML Kit Text Recognition**

## Outcome

Circle to Search is a Google system/product experience, not a callable OCR SDK for this application. The publicly supported integration is ML Kit's beta GenAI Prompt API backed by AICore and Gemini Nano. Google itself recommends Text Recognition first for extracting image text, with Prompt API used only for subsequent processing.

The beta dependency is intentionally not included in the production app. No compatible physical Android device is connected to this workspace (`flutter devices` reported Linux only), so Gemini-only and combined accuracy, latency, model variance, battery/quota, and offline behavior cannot be measured. An unavailable experiment is not evidence of improvement.

## Reproducible evidence

Run:

```sh
flutter test test/core
dart run tool/odometer_ocr_evaluator.dart
flutter devices
```

Frozen synthetic held-out results for the deterministic parser/scorer are 8/8 exact readable cases, 0 incorrect autofills, and 4/4 degraded or negative cases abstained. Device OCR and Gemini latency are explicitly unmeasured.

| Path | Held-out exact | Incorrect autofill | Availability | Decision |
| --- | ---: | ---: | --- | --- |
| Deterministic parser/scorer | 8/8 | 0 | Cross-device ML Kit path | Retain |
| Gemini Nano only | Not measured | Not measured | No supported test device | Do not ship |
| Combined | Not measured | Not measured | No supported test device | Do not ship |

## Public API constraints checked

- Prompt API is beta, has no SLA/deprecation guarantee, requires Android API 26+, and uses AICore: <https://developers.google.com/ml-kit/genai/prompt/android>
- Current setup dependency is `com.google.mlkit:genai-prompt:1.0.0-beta2`; image plus text input is supported: <https://developers.google.com/ml-kit/genai/prompt/android/get-started>
- Stable/full model selection must be followed by runtime `checkStatus`; availability cannot be assumed from the phone model: <https://developers.google.com/ml-kit/genai/prompt/android/select-model>
- Structured output is alpha, Kotlin-only, separately capability-gated, and requires KSP: <https://developers.google.com/ml-kit/genai/prompt/android/structured-output>
- Inference is on-device, but foreground-only and subject to busy/battery quota errors: <https://developers.google.com/ml-kit/genai>

## Required gate before reconsideration

Reopen only with supported physical devices and a pre-registered comparison against the frozen held-out corpus. Require zero incorrect autofills, repeated-run variance reporting, median/p95 latency, model/status/version telemetry without raw OCR or image logs, offline-after-download testing, and all failure states falling back to the deterministic outcome. A Gemini integer may only corroborate an existing deterministic candidate; it must never independently prefill or submit an odometer reading.

The Dart boundary in `odometer_secondary_recognizer.dart` is disabled by default and strictly rejects prose, numeric strings, floats, extra fields, contradictory states, and out-of-range readings. It adds no GenAI dependency and cannot change the current OCR outcome.
