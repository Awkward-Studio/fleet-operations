# Odometer OCR operations guide

## Scope and safety model

OCR assists only the starting and ending odometer fields. There is deliberately no number-plate recognition. A result is an editable suggestion, never evidence by itself and never an automatic submission. The driver must retain the captured photo, verify the displayed digits, and explicitly confirm them.

Outcomes are intentionally small:

- `ACCEPTED`: a sufficiently strong, unambiguous candidate may prefill.
- `NEEDS_REVIEW`: show alternatives or require manual entry; do not prefill.
- `NO_READING`: require manual entry and allow recapture.

Manual edits invalidate prior confirmation and change provenance to `MANUAL`. Selecting an OCR alternative records `OCR_CORRECTED`; accepting an unchanged prefill records `OCR_CONFIRMED`.

## Architecture and data flow

1. `OdometerCaptureField` captures a native-resolution camera image and lets the driver crop all odometer digits.
2. `OdometerImagePreprocessor` bakes EXIF orientation, strips metadata, measures image quality, and creates normalized, enhanced grayscale, and upscaled JPEG variants.
3. `MlKitOdometerTextRecognizer` runs on-device Latin text recognition for each variant.
4. `OdometerOcrParser` preserves line/block geometry and extracts digit candidates with substitution evidence.
5. `OdometerCandidateScorer` aggregates agreement and context, then accepts, abstains, or requests review.
6. `OdometerOcrCoordinator` serializes native calls, enforces an eight-second per-variant timeout, handles cancellation, and removes owned temporary files in `finally`.
7. The API locks authoritative trip rows, validates confirmation/provenance and the reference shown by the client, checks plausible deltas, persists privacy-safe audit fields, and only then mutates trip state.

Gemini Nano is disabled. Circle to Search is not an embeddable OCR API, and the available Gemini Prompt API was not shipped without representative physical-device evidence. See the feasibility decision for the reconsideration gate.

## Capture requirements

- Keep every odometer digit inside the crop with a small margin.
- Move close enough for a crop of at least 480×120 pixels.
- Hold the phone horizontally and steady; tap the digits to focus.
- Avoid glare, deep shadow, reflections, and washed-out LCD segments.
- Exclude trip meters, clocks, fuel range, warning codes, and dashboard labels where practical.
- If the app reports blur, exposure, contrast, glare, clipping, or size problems, retake instead of trusting a manual guess.

JPEG, PNG, and other formats decoded by the pinned Dart `image` package are accepted during preparation; generated variants are metadata-free JPEG at quality 95. The native camera source remains attached as trip evidence.

## Thresholds

Client scoring defaults:

| Guard | Value | Behavior |
| --- | ---: | --- |
| Acceptance score | 46 | Lower scores require review |
| Winner margin | 12 | Closer candidates require review |
| Start delta | 500 km | Larger values require review |
| End delta | 1,000 km | Larger values require review |
| Minimum crop | 480×120 px | Smaller images require recapture |
| Mean luminance | 38–222 | Outside the range requires recapture |
| Contrast deviation | 24 | Lower contrast requires recapture |
| Sharpness | 55 | Lower sharpness requires recapture |
| Maximum glare | 18% | More glare requires recapture |

The backend independently enforces `ODOMETER_MAX_START_DELTA_KM` (default 500) and `ODOMETER_MAX_TRIP_DELTA_KM` (default 1,000). Keep client limits equal to or stricter than server limits. Client scores are uncalibrated ranking signals and are neither transmitted nor trusted by the API.

## API provenance and overrides

Every new reading sends `reading_source`, `driver_confirmed`, `expected_reference_km`, `client_version`, optional `client_ocr_decision`, and an override flag/reason. The server stores separate start/end confirmation timestamps and audit provenance without raw recognized text.

Stale references, starts below the vehicle reading, non-increasing ends, and excessive deltas are rejected before evidence or operational state is persisted. Only an administrator or operations approver may submit an exceptional value, with `odometer_override=true` and a reason of at least ten characters. The server records the authorizing user and reason. Drivers should recapture or contact operations; limits must not be widened to make one reading pass.

## Privacy and diagnostics

Recognition and preprocessing are local. The OCR coordinator's diagnostic schema contains only event name, sequence ID, scan mode, elapsed milliseconds, variant count, cancellation, reason code, and cleanup status. Do not add recognized strings, candidate digits, file paths, image bytes, registration numbers, trip/customer identifiers, or OCR images to logs or telemetry.

Only the driver-confirmed number and captured evidence photo are transmitted through the existing authenticated trip operation. Temporary normalized variants are deleted after success, failure, timeout, or cancellation. Crash/restart cleanup and network inspection remain physical-device release checks.

## Corpus and reproducible validation

The frozen manifest is `test/fixtures/odometer_ocr/manifest.json`. It contains 60 synthetic, EXIF-stripped cases: ten each for mechanical, LCD, seven-segment, multi-number, degraded, and negative conditions. Real additions require documented consent and stripped EXIF.

```sh
flutter analyze
flutter test test/core test/features
dart run tool/odometer_ocr_evaluator.dart
flutter build apk --debug
```

Release gates are at least 95% exact match on readable clear held-out cases, at most 1% incorrect automatic prefill over the full corpus, all privacy/rollback tests passing, and device p95 latency within the agreed device budget. The evaluator reports baseline, parser, training, held-out, per-category, abstention, and optional latency metrics. Never tune thresholds on held-out cases.

## Device validation matrix

Before release, test start and end flows on at least two representative physical Android devices. Cover mechanical, LCD, seven-segment, multiple dashboard numbers, blur, glare, low light, clipped digits, manual correction, cancel/rescan/retake, repeated scans, offline-after-model-download, app restart, and large text/small screens. Record median/p95 latency, memory growth, exact match, incorrect prefill, abstention, and correction rate. Inspect `adb logcat` and captured network traffic for forbidden OCR text, paths, bytes, or unexpected requests.

No physical Android device was connected during the 2026-08-11 implementation run, so device latency, memory, crash cleanup, and network observations are explicitly unverified and remain a release blocker.

## Troubleshooting and rollback

- Frequent `imageQuality`: clean the display, improve lighting, refocus, and check crop dimensions before changing thresholds.
- Frequent ambiguity: inspect candidate evidence by synthetic fixture ID; do not log production text.
- Provider errors/timeouts: verify ML Kit packaging and device storage, then use manual confirmed entry.
- Stale-reference API conflict: refresh the trip and compare against the new authoritative value.
- Implausible-reading rejection: recapture; route genuine cluster replacement/maintenance exceptions to an authorized operations approver.
- Temporary-file growth: exercise cancellation/failure tests and inspect only the app-owned `odometer_ocr_` temporary directories.

Rollback is code-only: revert the OCR feature commit and rebuild. Do not reverse the provenance migration after production data exists; the added nullable/audit fields are backward-compatible and should remain for history. Existing confirmed trip readings and photos must never be deleted as part of an OCR rollback.
