import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:image/image.dart' as img;

import 'package:driver_app/core/odometer_image_preprocessor.dart';
import 'package:driver_app/core/odometer_ocr_contract.dart';

void main() {
  late Directory root;

  setUp(() async {
    root = await Directory.systemTemp.createTemp('odometer_preprocessor_test_');
  });

  tearDown(() async {
    if (await root.exists()) await root.delete(recursive: true);
  });

  test(
    'bakes EXIF rotation and writes a bounded ordered variant set',
    () async {
      final source = _sharpImage(width: 800, height: 300);
      source.exif.imageIfd.orientation = 6;
      final input = await _writeInput(root, source);
      final prepared = await OdometerImagePreprocessor(
        temporaryRoot: root,
      ).prepare(input.path);

      expect(prepared.width, 300);
      expect(prepared.height, 800);
      expect(
        prepared.variants.map((variant) => variant.kind),
        OdometerImageVariantKind.values,
      );
      expect(prepared.variants, hasLength(3));
      for (final variant in prepared.variants) {
        expect(await File(variant.path).exists(), isTrue);
      }

      final ownedPath = File(prepared.normalizedPath).parent.path;
      await prepared.dispose();
      await prepared.dispose();
      expect(await Directory(ownedPath).exists(), isFalse);
    },
  );

  test('flags a crop below the minimum dimensions', () async {
    final prepared = await _prepare(root, _sharpImage(width: 320, height: 100));
    expect(prepared.qualityIssues, contains(OdometerQualityIssue.tooSmall));
    expect(prepared.shouldRecognize, isFalse);
    await prepared.dispose();
  });

  test('flags clipped crop coverage', () async {
    final source = _sharpImage();
    final input = await _writeInput(root, source);
    final prepared = await OdometerImagePreprocessor(
      temporaryRoot: root,
    ).prepare(input.path, cropCoverage: 0.02);
    expect(prepared.qualityIssues, contains(OdometerQualityIssue.clipped));
    await prepared.dispose();
  });

  test('flags blur and low contrast', () async {
    final prepared = await _prepare(root, _solidImage(128));
    expect(prepared.qualityIssues, contains(OdometerQualityIssue.blurred));
    expect(prepared.qualityIssues, contains(OdometerQualityIssue.lowContrast));
    await prepared.dispose();
  });

  test('flags underexposure, overexposure, and glare', () async {
    final dark = await _prepare(root, _solidImage(5));
    expect(dark.qualityIssues, contains(OdometerQualityIssue.underexposed));
    await dark.dispose();

    final bright = await _prepare(root, _solidImage(252));
    expect(bright.qualityIssues, contains(OdometerQualityIssue.overexposed));
    expect(bright.qualityIssues, contains(OdometerQualityIssue.glare));
    await bright.dispose();
  });

  test('clear crop has no blocking quality issue', () async {
    final prepared = await _prepare(root, _sharpImage());
    expect(prepared.qualityIssues, isEmpty);
    expect(prepared.shouldRecognize, isTrue);
    expect(prepared.metrics.detailHeightFraction, greaterThan(0.5));
    await prepared.dispose();
  });

  test('variant bytes and dimensions are deterministic', () async {
    final input = await _writeInput(root, _sharpImage(width: 720, height: 240));
    final processor = OdometerImagePreprocessor(temporaryRoot: root);
    final first = await processor.prepare(input.path);
    final second = await processor.prepare(input.path);

    for (var index = 0; index < first.variants.length; index++) {
      expect(
        await File(first.variants[index].path).readAsBytes(),
        await File(second.variants[index].path).readAsBytes(),
      );
    }
    final upscaled = img.decodeImage(
      await File(first.variants.last.path).readAsBytes(),
    )!;
    expect(upscaled.width, 1200);
    expect(upscaled.height, 400);
    await first.dispose();
    await second.dispose();
  });

  test(
    'failure and cancellation remove their owned temporary directory',
    () async {
      final invalid = File('${root.path}${Platform.pathSeparator}bad.jpg');
      await invalid.writeAsString('not an image');
      final processor = OdometerImagePreprocessor(temporaryRoot: root);

      await expectLater(
        processor.prepare(invalid.path),
        throwsA(isA<OdometerImagePreparationException>()),
      );
      expect(await _ownedDirectories(root), isEmpty);

      final input = await _writeInput(root, _sharpImage());
      await expectLater(
        processor.prepare(input.path, isCancelled: () => true),
        throwsA(isA<OdometerImagePreparationException>()),
      );
      expect(await _ownedDirectories(root), isEmpty);
    },
  );

  test('every issue has an actionable recapture instruction', () {
    for (final issue in OdometerQualityIssue.values) {
      expect(OdometerImagePreprocessor.recaptureInstruction(issue), isNotEmpty);
    }
  });
}

Future<PreparedOdometerImage> _prepare(Directory root, img.Image image) async {
  final input = await _writeInput(root, image);
  return OdometerImagePreprocessor(temporaryRoot: root).prepare(input.path);
}

Future<File> _writeInput(Directory root, img.Image image) async {
  final file = File(
    '${root.path}${Platform.pathSeparator}input_${DateTime.now().microsecondsSinceEpoch}.jpg',
  );
  await file.writeAsBytes(img.encodeJpg(image, quality: 100));
  return file;
}

img.Image _sharpImage({int width = 720, int height = 240}) {
  final image = img.Image(width: width, height: height);
  for (var y = 0; y < height; y++) {
    for (var x = 0; x < width; x++) {
      final value = (x ~/ 8).isEven ? 25 : 225;
      image.setPixelRgb(x, y, value, value, value);
    }
  }
  return image;
}

img.Image _solidImage(int value) {
  final image = img.Image(width: 720, height: 240);
  for (final pixel in image) {
    pixel.setRgb(value, value, value);
  }
  return image;
}

Future<List<Directory>> _ownedDirectories(Directory root) async => root
    .list()
    .where(
      (entry) => entry is Directory && entry.path.contains('odometer_ocr_'),
    )
    .cast<Directory>()
    .toList();
