import 'dart:io';
import 'dart:math' as math;

import 'package:image/image.dart' as img;

import 'odometer_ocr_contract.dart';

enum OdometerImageVariantKind { normalized, enhanced, upscaled }

class OdometerImagePreparationConfig {
  const OdometerImagePreparationConfig({
    this.minimumWidth = 480,
    this.minimumHeight = 120,
    this.minimumAspectRatio = 1.4,
    this.maximumAspectRatio = 10,
    this.minimumCropCoverage = 0.08,
    this.minimumLuminance = 38,
    this.maximumLuminance = 222,
    this.minimumContrast = 24,
    this.minimumSharpness = 55,
    this.maximumGlareFraction = 0.18,
    this.upscaleMinimumWidth = 1200,
    this.jpegQuality = 95,
  });

  final int minimumWidth;
  final int minimumHeight;
  final double minimumAspectRatio;
  final double maximumAspectRatio;
  final double minimumCropCoverage;
  final double minimumLuminance;
  final double maximumLuminance;
  final double minimumContrast;
  final double minimumSharpness;
  final double maximumGlareFraction;
  final int upscaleMinimumWidth;
  final int jpegQuality;
}

class OdometerImageQualityMetrics {
  const OdometerImageQualityMetrics({
    required this.meanLuminance,
    required this.luminanceDeviation,
    required this.sharpness,
    required this.glareFraction,
    required this.detailHeightFraction,
  });

  final double meanLuminance;
  final double luminanceDeviation;
  final double sharpness;
  final double glareFraction;

  /// Fraction of sampled rows containing meaningful horizontal detail.
  /// This is an intentionally conservative proxy, not detected digit geometry.
  final double detailHeightFraction;
}

class PreparedOdometerImageVariant {
  const PreparedOdometerImageVariant({required this.kind, required this.path});

  final OdometerImageVariantKind kind;
  final String path;
}

class PreparedOdometerImage {
  PreparedOdometerImage._(
    this._ownedDirectory, {
    required this.normalizedPath,
    required this.variants,
    required this.width,
    required this.height,
    required this.metrics,
    required this.qualityIssues,
  });

  final String normalizedPath;
  final List<PreparedOdometerImageVariant> variants;
  final int width;
  final int height;
  final OdometerImageQualityMetrics metrics;
  final List<OdometerQualityIssue> qualityIssues;
  final Directory _ownedDirectory;
  bool _disposed = false;

  bool get shouldRecognize => qualityIssues.isEmpty;
  bool get isDisposed => _disposed;

  Future<void> dispose() async {
    if (_disposed) return;
    _disposed = true;
    if (await _ownedDirectory.exists()) {
      await _ownedDirectory.delete(recursive: true);
    }
  }
}

class OdometerImagePreparationException implements Exception {
  const OdometerImagePreparationException(this.message);

  final String message;

  @override
  String toString() => 'OdometerImagePreparationException: $message';
}

class OdometerImagePreprocessor {
  const OdometerImagePreprocessor({
    this.config = const OdometerImagePreparationConfig(),
    this.temporaryRoot,
  });

  final OdometerImagePreparationConfig config;
  final Directory? temporaryRoot;

  /// Decodes the crop, physically applies EXIF orientation, strips metadata,
  /// assesses legibility, and writes exactly three deterministic JPEG variants.
  /// The caller must dispose the returned object in a `finally` block.
  Future<PreparedOdometerImage> prepare(
    String path, {
    double cropCoverage = 1,
    bool Function()? isCancelled,
  }) async {
    final root = temporaryRoot ?? Directory.systemTemp;
    await root.create(recursive: true);
    final owned = await root.createTemp('odometer_ocr_');

    try {
      _throwIfCancelled(isCancelled);
      final bytes = await File(path).readAsBytes();
      final decoded = img.decodeImage(bytes);
      if (decoded == null) {
        throw const OdometerImagePreparationException(
          'The selected file is not a supported image.',
        );
      }

      _throwIfCancelled(isCancelled);
      final normalized = img.bakeOrientation(decoded).convert(numChannels: 3);
      normalized.exif = img.ExifData();
      normalized.iccProfile = null;
      final metrics = assess(normalized);
      final issues = _qualityIssues(normalized, metrics, cropCoverage);

      final normalizedPath = _child(owned, '01_normalized.jpg');
      await _writeJpeg(normalizedPath, normalized);

      _throwIfCancelled(isCancelled);
      final enhanced = img.adjustColor(
        img.grayscale(img.Image.from(normalized)),
        contrast: 1.35,
      );
      final enhancedPath = _child(owned, '02_enhanced.jpg');
      await _writeJpeg(enhancedPath, enhanced);

      _throwIfCancelled(isCancelled);
      final targetWidth = math.max(
        config.upscaleMinimumWidth,
        normalized.width,
      );
      final upscaled = img.copyResize(
        enhanced,
        width: targetWidth,
        interpolation: img.Interpolation.cubic,
      );
      final upscaledPath = _child(owned, '03_upscaled.jpg');
      await _writeJpeg(upscaledPath, upscaled);
      _throwIfCancelled(isCancelled);

      return PreparedOdometerImage._(
        owned,
        normalizedPath: normalizedPath,
        variants: List.unmodifiable([
          PreparedOdometerImageVariant(
            kind: OdometerImageVariantKind.normalized,
            path: normalizedPath,
          ),
          PreparedOdometerImageVariant(
            kind: OdometerImageVariantKind.enhanced,
            path: enhancedPath,
          ),
          PreparedOdometerImageVariant(
            kind: OdometerImageVariantKind.upscaled,
            path: upscaledPath,
          ),
        ]),
        width: normalized.width,
        height: normalized.height,
        metrics: metrics,
        qualityIssues: List.unmodifiable(issues),
      );
    } catch (_) {
      if (await owned.exists()) await owned.delete(recursive: true);
      rethrow;
    }
  }

  OdometerImageQualityMetrics assess(img.Image image) {
    final stride = math.max(1, math.max(image.width, image.height) ~/ 600);
    var count = 0;
    var sum = 0.0;
    var sumSquares = 0.0;
    var glare = 0;
    var gradientSum = 0.0;
    var gradientSquares = 0.0;
    var gradientCount = 0;
    final detailedRows = <int>{};

    for (var y = 0; y < image.height; y += stride) {
      for (var x = 0; x < image.width; x += stride) {
        final lum = _luminance(image.getPixel(x, y));
        count++;
        sum += lum;
        sumSquares += lum * lum;
        if (lum >= 245) glare++;
        if (x >= stride) {
          final delta = lum - _luminance(image.getPixel(x - stride, y));
          final magnitude = delta.abs();
          gradientSum += magnitude;
          gradientSquares += magnitude * magnitude;
          gradientCount++;
          if (magnitude >= 32) detailedRows.add(y);
        }
      }
    }

    final mean = count == 0 ? 0.0 : sum / count;
    final variance = count == 0
        ? 0.0
        : math.max(0.0, (sumSquares / count) - (mean * mean));
    final gradientMean = gradientCount == 0 ? 0.0 : gradientSum / gradientCount;
    final gradientVariance = gradientCount == 0
        ? 0.0
        : math.max(
            0.0,
            (gradientSquares / gradientCount) - (gradientMean * gradientMean),
          );
    final sampledRows = math.max(1, (image.height / stride).ceil());

    return OdometerImageQualityMetrics(
      meanLuminance: mean,
      luminanceDeviation: math.sqrt(variance),
      sharpness: gradientVariance,
      glareFraction: count == 0 ? 0 : glare / count,
      detailHeightFraction: detailedRows.length / sampledRows,
    );
  }

  List<OdometerQualityIssue> _qualityIssues(
    img.Image image,
    OdometerImageQualityMetrics metrics,
    double cropCoverage,
  ) {
    final issues = <OdometerQualityIssue>[];
    final aspect = image.width / image.height;
    if (image.width < config.minimumWidth ||
        image.height < config.minimumHeight) {
      issues.add(OdometerQualityIssue.tooSmall);
    }
    if (aspect < config.minimumAspectRatio ||
        aspect > config.maximumAspectRatio ||
        cropCoverage < config.minimumCropCoverage ||
        metrics.detailHeightFraction < 0.08) {
      issues.add(OdometerQualityIssue.clipped);
    }
    if (metrics.sharpness < config.minimumSharpness) {
      issues.add(OdometerQualityIssue.blurred);
    }
    if (metrics.meanLuminance < config.minimumLuminance) {
      issues.add(OdometerQualityIssue.underexposed);
    }
    if (metrics.meanLuminance > config.maximumLuminance) {
      issues.add(OdometerQualityIssue.overexposed);
    }
    if (metrics.luminanceDeviation < config.minimumContrast) {
      issues.add(OdometerQualityIssue.lowContrast);
    }
    if (metrics.glareFraction > config.maximumGlareFraction) {
      issues.add(OdometerQualityIssue.glare);
    }
    return issues;
  }

  static String recaptureInstruction(OdometerQualityIssue issue) =>
      switch (issue) {
        OdometerQualityIssue.tooSmall =>
          'Move closer so the odometer digits fill the guide.',
        OdometerQualityIssue.blurred =>
          'Hold the phone steady, tap the digits to focus, and retake.',
        OdometerQualityIssue.underexposed =>
          'Add light without casting a shadow over the display.',
        OdometerQualityIssue.overexposed || OdometerQualityIssue.glare =>
          'Change the camera angle to remove glare from the display.',
        OdometerQualityIssue.lowContrast =>
          'Clean the display and refocus so every digit edge is visible.',
        OdometerQualityIssue.clipped =>
          'Keep every odometer digit inside the guide with a small margin.',
        OdometerQualityIssue.unsupportedOrientation =>
          'Rotate the phone until the odometer is horizontal and retake.',
      };

  Future<void> _writeJpeg(String path, img.Image image) =>
      File(path).writeAsBytes(
        img.encodeJpg(image, quality: config.jpegQuality),
        flush: true,
      );

  static double _luminance(img.Pixel pixel) =>
      (0.2126 * pixel.r) + (0.7152 * pixel.g) + (0.0722 * pixel.b);

  static String _child(Directory directory, String name) =>
      '${directory.path}${Platform.pathSeparator}$name';

  static void _throwIfCancelled(bool Function()? isCancelled) {
    if (isCancelled?.call() ?? false) {
      throw const OdometerImagePreparationException('Preparation cancelled.');
    }
  }
}
