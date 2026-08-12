import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:driver_app/core/odometer_ocr_contract.dart';
import 'package:driver_app/features/trips/presentation/widgets/odometer_capture_field.dart';

void main() {
  testWidgets('accepted reading prefills but requires explicit confirmation', (
    tester,
  ) async {
    final controller = TextEditingController();
    OdometerCaptureSnapshot? snapshot;
    await _pump(
      tester,
      controller: controller,
      onChanged: (value) => snapshot = value,
      scan: (_) async => _outcome(OdometerOcrDecision.accepted, reading: 541),
    );

    await tester.tap(find.text('Capture odometer'));
    await tester.pumpAndSettle();
    expect(controller.text, '541');
    expect(snapshot!.source, OdometerReadingSource.ocrConfirmed);
    expect(snapshot!.canSubmit, isFalse);

    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    expect(snapshot!.confirmed, isTrue);
    expect(snapshot!.canSubmit, isTrue);
  });

  testWidgets('manual edit during delayed scan is never overwritten', (
    tester,
  ) async {
    final completion = Completer<OdometerOcrOutcome>();
    final controller = TextEditingController();
    OdometerCaptureSnapshot? snapshot;
    await _pump(
      tester,
      controller: controller,
      onChanged: (value) => snapshot = value,
      scan: (_) => completion.future,
    );

    await tester.tap(find.text('Capture odometer'));
    await tester.pump();
    await tester.enterText(find.byType(TextFormField).first, '777');
    completion.complete(_outcome(OdometerOcrDecision.accepted, reading: 541));
    await tester.pumpAndSettle();

    expect(controller.text, '777');
    expect(snapshot!.source, OdometerReadingSource.manual);
    expect(snapshot!.confirmed, isFalse);
  });

  testWidgets('needs-review alternatives require an explicit choice', (
    tester,
  ) async {
    final controller = TextEditingController();
    OdometerCaptureSnapshot? snapshot;
    await _pump(
      tester,
      controller: controller,
      onChanged: (value) => snapshot = value,
      scan: (_) async => _review([541, 547]),
    );
    await tester.tap(find.text('Capture odometer'));
    await tester.pumpAndSettle();
    expect(controller.text, isEmpty);
    expect(find.text('541 KM'), findsOneWidget);

    await tester.tap(find.text('541 KM'));
    await tester.pump();
    expect(controller.text, '541');
    expect(snapshot!.source, OdometerReadingSource.ocrCorrected);
  });

  testWidgets('no-reading and exceptions remain manual, reviewable states', (
    tester,
  ) async {
    final controller = TextEditingController();
    await _pump(
      tester,
      controller: controller,
      onChanged: (_) {},
      scan: (_) async => _outcome(OdometerOcrDecision.noReading),
    );
    await tester.tap(find.text('Capture odometer'));
    await tester.pumpAndSettle();
    expect(find.textContaining('No trustworthy reading'), findsOneWidget);

    final errorController = TextEditingController();
    await _pump(
      tester,
      controller: errorController,
      onChanged: (_) {},
      scan: (_) => Future.error(StateError('platform')),
    );
    await tester.tap(find.text('Capture odometer'));
    await tester.pumpAndSettle();
    expect(find.textContaining('scan failed'), findsOneWidget);
  });

  testWidgets('capture cancellation restores the prior idle state', (
    tester,
  ) async {
    final controller = TextEditingController();
    OdometerCaptureSnapshot? snapshot;
    await _pump(
      tester,
      controller: controller,
      onChanged: (value) => snapshot = value,
      capture: (_) async => null,
      scan: (_) async => _outcome(OdometerOcrDecision.noReading),
    );
    await tester.tap(find.text('Capture odometer'));
    await tester.pumpAndSettle();
    expect(snapshot!.state, OdometerCaptureState.idle);
    expect(find.textContaining('Opening camera'), findsNothing);
  });

  testWidgets('retake invalidates prior confirmation', (tester) async {
    final controller = TextEditingController();
    OdometerCaptureSnapshot? snapshot;
    var calls = 0;
    await _pump(
      tester,
      controller: controller,
      onChanged: (value) => snapshot = value,
      capture: (_) async => 'photo-${++calls}',
      scan: (_) async => _outcome(OdometerOcrDecision.accepted, reading: 541),
    );
    await tester.tap(find.text('Capture odometer'));
    await tester.pumpAndSettle();
    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    expect(snapshot!.confirmed, isTrue);

    await tester.tap(find.text('Retake'));
    await tester.pumpAndSettle();
    expect(snapshot!.photoPath, 'photo-2');
    expect(snapshot!.confirmed, isFalse);
  });

  testWidgets('cancelled scan cannot publish and the same photo can rescan', (
    tester,
  ) async {
    final first = Completer<OdometerOcrOutcome>();
    final controller = TextEditingController();
    var scans = 0;
    await _pump(
      tester,
      controller: controller,
      onChanged: (_) {},
      scan: (_) {
        scans++;
        return scans == 1
            ? first.future
            : Future.value(
                _outcome(OdometerOcrDecision.accepted, reading: 600),
              );
      },
    );
    await tester.tap(find.text('Capture odometer'));
    await tester.pump();
    await tester.tap(find.text('Cancel scan'));
    await tester.pump();
    first.complete(_outcome(OdometerOcrDecision.accepted, reading: 541));
    await tester.pumpAndSettle();
    expect(controller.text, isEmpty);

    await tester.tap(find.text('Rescan'));
    await tester.pumpAndSettle();
    expect(controller.text, '600');
  });

  testWidgets('end mode validates strict increase', (tester) async {
    final key = GlobalKey<FormState>();
    final controller = TextEditingController(text: '500');
    await _pump(
      tester,
      controller: controller,
      onChanged: (_) {},
      scan: (_) async => _outcome(OdometerOcrDecision.noReading),
      mode: OdometerScanMode.end,
      formKey: key,
    );
    expect(key.currentState!.validate(), isFalse);
    await tester.pump();
    expect(find.textContaining('greater than starting'), findsOneWidget);
  });

  testWidgets('small screen and large text render without overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(2)),
        child: MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: OdometerCaptureField(
                controller: TextEditingController(),
                mode: OdometerScanMode.start,
                referenceKm: 500,
                capturePhoto: (_) async => null,
                scan: (_, _) async => _outcome(OdometerOcrDecision.noReading),
                photoBuilder: (_, _) => const ColoredBox(color: Colors.black),
                onChanged: (_) {},
              ),
            ),
          ),
        ),
      ),
    );
    expect(tester.takeException(), isNull);
    expect(find.bySemanticsLabel('Capture odometer photo'), findsOneWidget);
  });
}

Future<void> _pump(
  WidgetTester tester, {
  required TextEditingController controller,
  required ValueChanged<OdometerCaptureSnapshot> onChanged,
  required Future<OdometerOcrOutcome> Function(OdometerOcrRequest) scan,
  Future<String?> Function(BuildContext)? capture,
  OdometerScanMode mode = OdometerScanMode.start,
  GlobalKey<FormState>? formKey,
}) => tester.pumpWidget(
  MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: Form(
          key: formKey,
          child: OdometerCaptureField(
            key: ValueKey(controller),
            controller: controller,
            mode: mode,
            referenceKm: 500,
            capturePhoto: capture ?? (_) async => 'photo-1',
            scan: (request, _) => scan(request),
            photoBuilder: (_, _) => const ColoredBox(color: Colors.black),
            onChanged: onChanged,
          ),
        ),
      ),
    ),
  ),
);

OdometerOcrOutcome _outcome(OdometerOcrDecision decision, {int? reading}) =>
    OdometerOcrOutcome(
      decision: decision,
      reasonCode: decision == OdometerOcrDecision.accepted
          ? OdometerOcrReasonCode.accepted
          : OdometerOcrReasonCode.noCandidate,
      selectedReadingKm: reading,
      candidates: reading == null ? const [] : [_candidate(reading)],
      qualityIssues: const [],
      elapsed: Duration.zero,
    );

OdometerOcrOutcome _review(List<int> readings) => OdometerOcrOutcome(
  decision: OdometerOcrDecision.needsReview,
  reasonCode: OdometerOcrReasonCode.ambiguous,
  candidates: readings.map(_candidate).toList(),
  qualityIssues: const [],
  elapsed: Duration.zero,
);

OdometerOcrCandidate _candidate(int reading) => OdometerOcrCandidate(
  readingKm: reading,
  score: 50,
  evidence: const OdometerCandidateEvidence(
    extractors: {'fixture'},
    variantCount: 1,
    relativeDigitHeight: 0.3,
    cropCentrality: 1,
    hasDistanceUnit: true,
    substitutionCount: 0,
  ),
);
