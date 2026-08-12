import 'package:flutter_test/flutter_test.dart';

import 'package:driver_app/core/odometer_ocr_contract.dart';
import 'package:driver_app/core/odometer_ocr_coordinator.dart';
import 'package:driver_app/core/odometer_ocr_parser.dart';

void main() {
  test('runs the bounded pipeline and always cleans prepared images', () async {
    final preparer = _FakePreparer();
    final recognizer = _FakeRecognizer();
    final sink = _CollectingSink();
    final coordinator = OdometerOcrCoordinator(
      preparer: preparer,
      recognizer: recognizer,
      diagnostics: sink,
    );

    final outcome = await coordinator.scan(_request());
    expect(outcome.decision, OdometerOcrDecision.accepted);
    expect(outcome.selectedReadingKm, 541);
    expect(recognizer.calls, 3);
    expect(preparer.cleanups, 1);
    expect(sink.events, hasLength(1));
    expect(sink.events.single.keys, isNot(contains('image_path')));
    expect(sink.events.single.toString(), isNot(contains('ODO 541')));
    expect(sink.events.single['reason_code'], 'accepted');
    await coordinator.close();
    await coordinator.close();
    expect(recognizer.closes, 1);
  });

  test(
    'cleanup failure is redacted and cannot replace the OCR outcome',
    () async {
      final sink = _CollectingSink();
      final coordinator = OdometerOcrCoordinator(
        preparer: _FakePreparer(cleanupError: true),
        recognizer: _FakeRecognizer(),
        diagnostics: sink,
      );
      final outcome = await coordinator.scan(_request());
      expect(outcome.decision, OdometerOcrDecision.accepted);
      expect(sink.events.single['cleanup_failed'], isTrue);
      await coordinator.close();
    },
  );

  test('quality failure short-circuits recognition and still cleans', () async {
    final preparer = _FakePreparer(
      qualityIssues: const [OdometerQualityIssue.blurred],
    );
    final recognizer = _FakeRecognizer();
    final coordinator = OdometerOcrCoordinator(
      preparer: preparer,
      recognizer: recognizer,
    );
    final outcome = await coordinator.scan(_request());
    expect(outcome.reasonCode, OdometerOcrReasonCode.imageQuality);
    expect(recognizer.calls, 0);
    expect(preparer.cleanups, 1);
    await coordinator.close();
  });

  test('provider error and timeout fail shut and clean up', () async {
    for (final recognizer in [
      _FakeRecognizer(error: StateError('platform')),
      _FakeRecognizer(delay: const Duration(milliseconds: 50)),
    ]) {
      final preparer = _FakePreparer();
      final coordinator = OdometerOcrCoordinator(
        preparer: preparer,
        recognizer: recognizer,
        recognitionTimeout: const Duration(milliseconds: 5),
      );
      final outcome = await coordinator.scan(_request());
      expect(outcome.decision, OdometerOcrDecision.noReading);
      expect(outcome.reasonCode, OdometerOcrReasonCode.providerError);
      expect(preparer.cleanups, 1);
      await coordinator.close();
    }
  });

  test('cancellation prevents a stale result from being published', () async {
    final token = OdometerCancellationToken();
    final preparer = _FakePreparer();
    final coordinator = OdometerOcrCoordinator(
      preparer: preparer,
      recognizer: _FakeRecognizer(delay: const Duration(milliseconds: 20)),
    );
    final pending = coordinator.scan(_request(), cancellationToken: token);
    await Future<void>.delayed(const Duration(milliseconds: 5));
    token.cancel();
    final outcome = await pending;
    expect(outcome.reasonCode, OdometerOcrReasonCode.cancelled);
    expect(outcome.selectedReadingKm, isNull);
    expect(preparer.cleanups, 1);
    await coordinator.close();
  });

  test('concurrent requests are serialized around the recognizer', () async {
    final recognizer = _FakeRecognizer(delay: const Duration(milliseconds: 5));
    final coordinator = OdometerOcrCoordinator(
      preparer: _FakePreparer(),
      recognizer: recognizer,
    );
    await Future.wait([
      coordinator.scan(_request()),
      coordinator.scan(_request()),
      coordinator.scan(_request()),
    ]);
    expect(recognizer.maximumActive, 1);
    await coordinator.close();
  });

  test(
    'closed coordinator rejects new work and closes provider once',
    () async {
      final recognizer = _FakeRecognizer();
      final coordinator = OdometerOcrCoordinator(
        preparer: _FakePreparer(),
        recognizer: recognizer,
      );
      await coordinator.close();
      await expectLater(coordinator.scan(_request()), throwsStateError);
      expect(recognizer.closes, 1);
    },
  );
}

OdometerOcrRequest _request() => const OdometerOcrRequest(
  imagePath: '/private/source.jpg',
  mode: OdometerScanMode.start,
  referenceKm: 500,
);

class _FakePreparer implements OdometerImagePreparationGateway {
  _FakePreparer({this.qualityIssues = const [], this.cleanupError = false});
  final List<OdometerQualityIssue> qualityIssues;
  final bool cleanupError;
  int cleanups = 0;

  @override
  Future<OdometerPreparedScan> prepare(
    String imagePath, {
    required bool Function() isCancelled,
  }) async => OdometerPreparedScan(
    variants: const [
      OdometerPreparedVariant(name: 'normalized', path: '/tmp/one.jpg'),
      OdometerPreparedVariant(name: 'enhanced', path: '/tmp/two.jpg'),
      OdometerPreparedVariant(name: 'upscaled', path: '/tmp/three.jpg'),
    ],
    width: 1000,
    height: 300,
    qualityIssues: qualityIssues,
    cleanup: () async {
      cleanups++;
      if (cleanupError) throw StateError('private cleanup path');
    },
  );
}

class _FakeRecognizer implements OdometerTextRecognitionGateway {
  _FakeRecognizer({this.delay = Duration.zero, this.error});
  final Duration delay;
  final Object? error;
  int calls = 0;
  int closes = 0;
  int _active = 0;
  int maximumActive = 0;

  @override
  Future<OdometerOcrDocumentInput> recognize(
    String imagePath, {
    required String variant,
  }) async {
    calls++;
    _active++;
    if (_active > maximumActive) maximumActive = _active;
    try {
      await Future<void>.delayed(delay);
      if (error != null) throw error!;
      return OdometerOcrDocumentInput(
        variant: variant,
        blocks: const [
          OdometerOcrBlockInput(
            lines: [OdometerOcrLineInput(text: 'ODO 541 km')],
          ),
        ],
      );
    } finally {
      _active--;
    }
  }

  @override
  Future<void> close() async => closes++;
}

class _CollectingSink implements OdometerDiagnosticSink {
  final events = <Map<String, Object?>>[];
  @override
  void record(Map<String, Object?> event) => events.add(event);
}
