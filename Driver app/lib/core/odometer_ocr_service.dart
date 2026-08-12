import 'mlkit_odometer_text_recognizer.dart';
import 'odometer_ocr_contract.dart';
import 'odometer_ocr_coordinator.dart';

export 'odometer_ocr_contract.dart' show OdometerScanMode;

class OdometerOcrResult {
  const OdometerOcrResult({required this.outcome});

  final OdometerOcrOutcome outcome;
  int? get readingKm => outcome.selectedReadingKm;
  List<int> get candidates =>
      outcome.candidates.map((candidate) => candidate.readingKm).toList();
  bool get hasReading => outcome.mayPrefill;
}

/// Compatibility facade used by the current trip screens. New UI code should
/// inject [OdometerOcrCoordinator] directly so it can cancel and close scans.
class OdometerOcrService {
  const OdometerOcrService._();

  static final OdometerOcrCoordinator _coordinator = OdometerOcrCoordinator(
    preparer: DefaultOdometerImagePreparationGateway(),
    recognizer: MlKitOdometerTextRecognizer(),
  );

  static Future<OdometerOcrResult> readOdometerKm(
    String imagePath, {
    int? minimumKm,
    OdometerScanMode mode = OdometerScanMode.start,
    OdometerCancellationToken? cancellationToken,
  }) async {
    final outcome = await _coordinator.scan(
      OdometerOcrRequest(
        imagePath: imagePath,
        mode: mode,
        referenceKm: minimumKm ?? 0,
      ),
      cancellationToken: cancellationToken,
    );
    return OdometerOcrResult(outcome: outcome);
  }

  static Future<void> close() => _coordinator.close();
}
