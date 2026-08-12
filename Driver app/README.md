# Index Fleet driver app

Flutter driver workflow for assigned trips, OTP verification, location tracking, inspections, and trip completion.

## Odometer OCR

The app uses on-device ML Kit Text Recognition only for start/end odometer assistance. It has no number-plate recognizer and never treats OCR as authoritative: only a high-evidence result may prefill, and the driver must compare it with the photo and confirm it before submission.

See [docs/odometer_ocr_operations.md](docs/odometer_ocr_operations.md) for architecture, thresholds, testing, capture guidance, privacy, overrides, troubleshooting, and release gates. The evaluated Gemini Nano decision is in [docs/odometer_gemini_nano_feasibility.md](docs/odometer_gemini_nano_feasibility.md).

## Development

```sh
flutter pub get
flutter analyze
flutter test
dart run tool/odometer_ocr_evaluator.dart
flutter build apk --debug
```

The backend must be reachable at the API base configured by the app. Odometer submissions use provenance contract `driver-app/1.0.0+1`; update that value when the application version changes.
