import 'package:driver_app/core/odometer_ocr_contract.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('accepted outcomes are the only outcomes allowed to prefill', () {
    const accepted = OdometerOcrOutcome(
      decision: OdometerOcrDecision.accepted,
      reasonCode: OdometerOcrReasonCode.accepted,
      selectedReadingKm: 541,
      candidates: [],
      qualityIssues: [],
      elapsed: Duration(milliseconds: 10),
    );
    const review = OdometerOcrOutcome(
      decision: OdometerOcrDecision.needsReview,
      reasonCode: OdometerOcrReasonCode.ambiguous,
      candidates: [],
      qualityIssues: [],
      elapsed: Duration(milliseconds: 10),
    );

    expect(accepted.mayPrefill, isTrue);
    expect(review.mayPrefill, isFalse);
  });
}
