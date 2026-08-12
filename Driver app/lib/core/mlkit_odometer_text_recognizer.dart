import 'dart:ui';

import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';

import 'odometer_ocr_coordinator.dart';
import 'odometer_ocr_parser.dart';

class MlKitOdometerTextRecognizer implements OdometerTextRecognitionGateway {
  MlKitOdometerTextRecognizer()
    : _recognizer = TextRecognizer(script: TextRecognitionScript.latin);

  final TextRecognizer _recognizer;
  bool _closed = false;

  @override
  Future<OdometerOcrDocumentInput> recognize(
    String imagePath, {
    required String variant,
  }) async {
    if (_closed) throw StateError('Text recognizer is closed.');
    final recognized = await _recognizer.processImage(
      InputImage.fromFilePath(imagePath),
    );
    return OdometerOcrDocumentInput(
      variant: variant,
      blocks: [
        for (final block in recognized.blocks)
          OdometerOcrBlockInput(
            lines: [
              for (final line in block.lines)
                OdometerOcrLineInput(
                  text: line.text,
                  bounds: _rect(line.boundingBox),
                  elements: [
                    for (final element in line.elements)
                      OdometerOcrElementInput(
                        text: element.text,
                        bounds: _rect(element.boundingBox),
                      ),
                  ],
                ),
            ],
          ),
      ],
    );
  }

  OdometerOcrRect _rect(Rect rect) => OdometerOcrRect(
    left: rect.left.toDouble(),
    top: rect.top.toDouble(),
    right: rect.right.toDouble(),
    bottom: rect.bottom.toDouble(),
  );

  @override
  Future<void> close() async {
    if (_closed) return;
    _closed = true;
    await _recognizer.close();
  }
}
