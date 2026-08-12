import 'package:flutter_test/flutter_test.dart';

import 'package:driver_app/core/odometer_secondary_recognizer.dart';

void main() {
  test('disabled provider is an immediate deterministic fallback', () async {
    const provider = DisabledOdometerSecondaryRecognizer();
    expect(await provider.checkStatus(), OdometerSecondaryStatus.disabled);
    final result = await provider.recognize(
      preparedImagePath: 'unused.jpg',
      deterministicSummary: '541 from ML Kit',
      referenceKm: 500,
      mode: 'START',
    );
    expect(result.status, OdometerSecondaryStatus.disabled);
    expect(result.isUsableEvidence, isFalse);
  });

  test('strict structured output accepts integer or explicit no-reading', () {
    final reading = parseSecondaryStructuredOutput(
      '{"reading_km":541,"is_odometer":true,"reason_code":"ODO_LABEL"}',
      modelVersion: 'test-model',
    );
    final noReading = parseSecondaryStructuredOutput(
      '{"reading_km":null,"is_odometer":false,"reason_code":"NO_DISPLAY"}',
    );
    expect(reading.readingKm, 541);
    expect(reading.isUsableEvidence, isTrue);
    expect(reading.modelVersion, 'test-model');
    expect(noReading.status, OdometerSecondaryStatus.available);
    expect(noReading.isUsableEvidence, isFalse);
  });

  for (final malformed in const [
    '541',
    'The reading is 541',
    '{"reading_km":"541","is_odometer":true,"reason_code":"X"}',
    '{"reading_km":541.0,"is_odometer":true,"reason_code":"X"}',
    '{"reading_km":0,"is_odometer":true,"reason_code":"X"}',
    '{"reading_km":541,"is_odometer":false,"reason_code":"X"}',
    '{"reading_km":541,"is_odometer":true,"reason_code":"X","extra":1}',
    '{broken json',
  ]) {
    test('fails shut for malformed output: $malformed', () {
      final result = parseSecondaryStructuredOutput(malformed);
      expect(result.status, OdometerSecondaryStatus.malformedOutput);
      expect(result.readingKm, isNull);
      expect(result.isUsableEvidence, isFalse);
    });
  }
}
