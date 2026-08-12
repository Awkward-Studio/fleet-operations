import 'dart:convert';

import 'odometer_ocr_contract.dart';
import 'odometer_ocr_parser.dart';
import 'odometer_ocr_scorer.dart';

const _allowedDisplayTypes = <String>{
  'mechanical',
  'lcd',
  'seven_segment',
  'multi_number',
  'degraded',
  'negative',
};

class OdometerCorpus {
  const OdometerCorpus({
    required this.schemaVersion,
    required this.corpusVersion,
    required this.cases,
  });

  final int schemaVersion;
  final String corpusVersion;
  final List<OdometerCorpusCase> cases;

  factory OdometerCorpus.fromJson(Map<String, Object?> json) {
    final rawCases = json['cases'];
    if (json['schema_version'] != 1 || rawCases is! List<Object?>) {
      throw const FormatException('Unsupported odometer corpus schema.');
    }
    final corpus = OdometerCorpus(
      schemaVersion: 1,
      corpusVersion: _requiredString(json, 'corpus_version'),
      cases: rawCases
          .map((item) => OdometerCorpusCase.fromJson(_object(item, 'case')))
          .toList(growable: false),
    );
    corpus.validate();
    return corpus;
  }

  void validate() {
    if (cases.length < 60) {
      throw FormatException(
        'Corpus needs at least 60 cases; found ${cases.length}.',
      );
    }
    final ids = <String>{};
    final categories = <String, int>{};
    for (final fixture in cases) {
      if (!ids.add(fixture.id)) {
        throw FormatException('Duplicate corpus id: ${fixture.id}.');
      }
      categories.update(
        fixture.displayType,
        (count) => count + 1,
        ifAbsent: () => 1,
      );
    }
    for (final category in _allowedDisplayTypes) {
      if ((categories[category] ?? 0) < 10) {
        throw FormatException('$category needs at least 10 cases.');
      }
    }
  }
}

class OdometerCorpusCase {
  const OdometerCorpusCase({
    required this.id,
    required this.expectedKm,
    required this.referenceKm,
    required this.mode,
    required this.expectedDecision,
    required this.displayType,
    required this.tags,
    required this.recognizedLines,
    required this.privacy,
    required this.decimalNotation,
    required this.units,
  });

  final String id;
  final int? expectedKm;
  final int referenceKm;
  final OdometerScanMode mode;
  final OdometerOcrDecision expectedDecision;
  final String displayType;
  final Set<String> tags;
  final List<String> recognizedLines;
  final CorpusPrivacy privacy;
  final String decimalNotation;
  final String units;

  factory OdometerCorpusCase.fromJson(Map<String, Object?> json) {
    final expectedKm = json['expected_km'];
    final referenceKm = json['reference_km'];
    final tags = json['tags'];
    final lines = json['recognized_lines'];
    if (expectedKm != null && expectedKm is! int) {
      throw FormatException(
        '${json['id']}: expected_km must be an integer or null.',
      );
    }
    final expectedKmValue = expectedKm as int?;
    if (referenceKm is! int || referenceKm < 0) {
      throw FormatException('${json['id']}: invalid reference_km.');
    }
    if (tags is! List<Object?> || lines is! List<Object?>) {
      throw FormatException(
        '${json['id']}: tags and recognized_lines are required.',
      );
    }
    final displayType = _requiredString(json, 'display_type');
    if (!_allowedDisplayTypes.contains(displayType)) {
      throw FormatException('${json['id']}: unsupported display type.');
    }
    final expectedDecision = _decision(
      _requiredString(json, 'expected_decision'),
    );
    if (expectedDecision == OdometerOcrDecision.accepted &&
        expectedKmValue == null) {
      throw FormatException('${json['id']}: accepted requires expected_km.');
    }
    if (expectedKmValue != null &&
        (expectedKmValue < 1 || expectedKmValue > 9_999_999)) {
      throw FormatException(
        '${json['id']}: expected_km is outside fleet bounds.',
      );
    }
    return OdometerCorpusCase(
      id: _requiredString(json, 'id'),
      expectedKm: expectedKmValue,
      referenceKm: referenceKm,
      mode: _mode(_requiredString(json, 'mode')),
      expectedDecision: expectedDecision,
      displayType: displayType,
      tags: tags.map((value) => value.toString()).toSet(),
      recognizedLines: lines.map((value) => value.toString()).toList(),
      privacy: CorpusPrivacy.fromJson(_object(json['privacy'], 'privacy')),
      decimalNotation: _requiredString(json, 'decimal_notation'),
      units: _requiredString(json, 'units'),
    );
  }
}

class CorpusPrivacy {
  const CorpusPrivacy({
    required this.classification,
    required this.consent,
    required this.exifStripped,
  });

  final String classification;
  final String consent;
  final bool exifStripped;

  factory CorpusPrivacy.fromJson(Map<String, Object?> json) {
    final classification = _requiredString(json, 'classification');
    final consent = _requiredString(json, 'consent');
    final exifStripped = json['exif_stripped'];
    if (!{'synthetic', 'sanitized_real'}.contains(classification) ||
        !{'not_required', 'recorded'}.contains(consent) ||
        exifStripped is! bool) {
      throw const FormatException('Invalid fixture privacy declaration.');
    }
    if (classification == 'sanitized_real' &&
        (consent != 'recorded' || !exifStripped)) {
      throw const FormatException(
        'Real fixtures require recorded consent and stripped EXIF.',
      );
    }
    return CorpusPrivacy(
      classification: classification,
      consent: consent,
      exifStripped: exifStripped,
    );
  }
}

class OdometerEvaluationPrediction {
  const OdometerEvaluationPrediction({
    required this.decision,
    this.readingKm,
    this.latency,
  }) : assert(
         decision == OdometerOcrDecision.accepted
             ? readingKm != null
             : readingKm == null,
       );

  final OdometerOcrDecision decision;
  final int? readingKm;
  final Duration? latency;
}

typedef OdometerFixturePredictor =
    OdometerEvaluationPrediction Function(OdometerCorpusCase fixture);

class OdometerEvaluationReport {
  const OdometerEvaluationReport({
    required this.corpusVersion,
    required this.total,
    required this.readable,
    required this.exactMatches,
    required this.decisionMatches,
    required this.incorrectAutofills,
    required this.abstentions,
    required this.latenciesMicros,
    required this.byCategory,
  });

  final String corpusVersion;
  final int total;
  final int readable;
  final int exactMatches;
  final int decisionMatches;
  final int incorrectAutofills;
  final int abstentions;
  final List<int> latenciesMicros;
  final Map<String, OdometerCategoryMetrics> byCategory;

  double get exactMatchRate => readable == 0 ? 0 : exactMatches / readable;
  double get incorrectAutofillRate =>
      total == 0 ? 0 : incorrectAutofills / total;
  double get abstentionRate => total == 0 ? 0 : abstentions / total;

  Map<String, Object?> toJson() => {
    'corpus_version': corpusVersion,
    'total': total,
    'readable': readable,
    'exact_matches': exactMatches,
    'exact_match_rate': exactMatchRate,
    'decision_matches': decisionMatches,
    'incorrect_autofills': incorrectAutofills,
    'incorrect_autofill_rate': incorrectAutofillRate,
    'abstentions': abstentions,
    'abstention_rate': abstentionRate,
    'latency': _latencyJson(latenciesMicros),
    'by_category': {
      for (final entry in byCategory.entries) entry.key: entry.value.toJson(),
    },
  };
}

class OdometerCategoryMetrics {
  int total = 0;
  int readable = 0;
  int exactMatches = 0;
  int incorrectAutofills = 0;
  int abstentions = 0;

  Map<String, Object> toJson() => {
    'total': total,
    'readable': readable,
    'exact_matches': exactMatches,
    'incorrect_autofills': incorrectAutofills,
    'abstentions': abstentions,
  };
}

OdometerCorpus decodeOdometerCorpus(String source) {
  final decoded = jsonDecode(source);
  return OdometerCorpus.fromJson(_object(decoded, 'corpus'));
}

OdometerEvaluationReport evaluateOdometerCorpus(
  OdometerCorpus corpus,
  OdometerFixturePredictor predictor,
) {
  var readable = 0;
  var exactMatches = 0;
  var decisionMatches = 0;
  var incorrectAutofills = 0;
  var abstentions = 0;
  final latencies = <int>[];
  final categories = <String, OdometerCategoryMetrics>{};

  for (final fixture in corpus.cases) {
    final prediction = predictor(fixture);
    final category = categories.putIfAbsent(
      fixture.displayType,
      OdometerCategoryMetrics.new,
    );
    category.total++;
    if (fixture.expectedDecision == OdometerOcrDecision.accepted) {
      readable++;
      category.readable++;
    }
    if (fixture.expectedDecision == OdometerOcrDecision.accepted &&
        prediction.readingKm == fixture.expectedKm) {
      exactMatches++;
      category.exactMatches++;
    }
    if (prediction.decision == fixture.expectedDecision) decisionMatches++;
    if (prediction.decision == OdometerOcrDecision.accepted &&
        prediction.readingKm != fixture.expectedKm) {
      incorrectAutofills++;
      category.incorrectAutofills++;
    }
    if (prediction.decision != OdometerOcrDecision.accepted) {
      abstentions++;
      category.abstentions++;
    }
    if (prediction.latency != null) {
      latencies.add(prediction.latency!.inMicroseconds);
    }
  }

  return OdometerEvaluationReport(
    corpusVersion: corpus.corpusVersion,
    total: corpus.cases.length,
    readable: readable,
    exactMatches: exactMatches,
    decisionMatches: decisionMatches,
    incorrectAutofills: incorrectAutofills,
    abstentions: abstentions,
    latenciesMicros: latencies,
    byCategory: categories,
  );
}

class OdometerParserEvaluationReport {
  const OdometerParserEvaluationReport({
    required this.total,
    required this.expectedCandidateCases,
    required this.unexpectedCandidateCases,
    required this.diagnostics,
  });

  final int total;
  final int expectedCandidateCases;
  final int unexpectedCandidateCases;

  /// Fixture ID to evidence-bearing unexpected parser candidates.
  final Map<String, List<Map<String, Object?>>> diagnostics;

  Map<String, Object?> toJson() => {
    'total': total,
    'expected_candidate_cases': expectedCandidateCases,
    'expected_candidate_rate': total == 0 ? 0 : expectedCandidateCases / total,
    'unexpected_candidate_cases': unexpectedCandidateCases,
    'diagnostics': diagnostics,
  };
}

OdometerParserEvaluationReport evaluateParserCorpus(
  OdometerCorpus corpus, {
  OdometerOcrParser parser = const OdometerOcrParser(),
}) {
  var expectedCandidateCases = 0;
  var unexpectedCandidateCases = 0;
  final diagnostics = <String, List<Map<String, Object?>>>{};

  for (final fixture in corpus.cases) {
    final parsed = parser.parse(
      OdometerOcrDocumentInput(
        variant: 'fixture-observation',
        blocks: [
          OdometerOcrBlockInput(
            lines: [
              for (final line in fixture.recognizedLines)
                OdometerOcrLineInput(text: line),
            ],
          ),
        ],
      ),
    );
    if (fixture.expectedKm != null &&
        parsed.any((candidate) => candidate.readingKm == fixture.expectedKm)) {
      expectedCandidateCases++;
    }
    final unexpected = parsed
        .where((candidate) => candidate.readingKm != fixture.expectedKm)
        .map(
          (candidate) => <String, Object?>{
            'reading_km': candidate.readingKm,
            'source_text': candidate.sourceText,
            'block_index': candidate.blockIndex,
            'line_index': candidate.lineIndex,
            'substitutions': candidate.substitutions.length,
          },
        )
        .toList(growable: false);
    if (unexpected.isNotEmpty) {
      unexpectedCandidateCases++;
      diagnostics[fixture.id] = unexpected;
    }
  }

  return OdometerParserEvaluationReport(
    total: corpus.cases.length,
    expectedCandidateCases: expectedCandidateCases,
    unexpectedCandidateCases: unexpectedCandidateCases,
    diagnostics: Map.unmodifiable(diagnostics),
  );
}

/// Frozen approximation of the pre-fix text fallback and rank policy.
///
/// This intentionally preserves its lossy behavior so the fixture corpus has
/// a reproducible baseline. It must not be used by production OCR.
OdometerEvaluationPrediction legacyTextBaseline(OdometerCorpusCase fixture) {
  final candidates = <int>{};
  for (final line in fixture.recognizedLines) {
    candidates.addAll(_legacyCandidates(line, fixture.referenceKm));
  }
  candidates.addAll(
    _legacyCandidates(fixture.recognizedLines.join('\n'), fixture.referenceKm),
  );
  final ranked = candidates.toList()
    ..sort(
      (a, b) => (a - fixture.referenceKm).abs().compareTo(
        (b - fixture.referenceKm).abs(),
      ),
    );
  return OdometerEvaluationPrediction(
    decision: ranked.isEmpty
        ? OdometerOcrDecision.noReading
        : OdometerOcrDecision.accepted,
    readingKm: ranked.isEmpty ? null : ranked.first,
  );
}

OdometerEvaluationPrediction parserScoringBaseline(OdometerCorpusCase fixture) {
  final observations = const OdometerOcrParser().parse(
    OdometerOcrDocumentInput(
      variant: 'fixture-observation',
      blocks: [
        OdometerOcrBlockInput(
          lines: [
            for (final line in fixture.recognizedLines)
              OdometerOcrLineInput(text: line),
          ],
        ),
      ],
    ),
  );
  final outcome = const OdometerCandidateScorer().decide(
    OdometerScoringInput(
      request: OdometerOcrRequest(
        imagePath: 'fixture-observation',
        mode: fixture.mode,
        referenceKm: fixture.referenceKm,
      ),
      observations: observations,
    ),
  );
  return OdometerEvaluationPrediction(
    decision: outcome.decision,
    readingKm: outcome.decision == OdometerOcrDecision.accepted
        ? outcome.selectedReadingKm
        : null,
  );
}

/// Stable 80/20 split by manifest order. Thresholds are tuned only on the
/// training partition; the held-out partition is reserved for final reporting.
OdometerCorpus corpusPartition(
  OdometerCorpus corpus, {
  required bool heldOut,
}) => OdometerCorpus(
  schemaVersion: corpus.schemaVersion,
  corpusVersion: '${corpus.corpusVersion}.${heldOut ? 'held-out' : 'training'}',
  cases: [
    for (var index = 0; index < corpus.cases.length; index++)
      if ((index % 5 == 0) == heldOut) corpus.cases[index],
  ],
);

Iterable<int> _legacyCandidates(String text, int minimumKm) sync* {
  final normalized = text
      .replaceAll(RegExp(r'[OoQqDd]'), '0')
      .replaceAll(RegExp(r'[Il|!]'), '1')
      .replaceAll(RegExp(r'[Ss]'), '5')
      .replaceAll(RegExp(r'[Bb]'), '8')
      .replaceAll(RegExp(r'[Zz]'), '2')
      .replaceAllMapped(
        RegExp(r'(\d)[^\d\s,.]{1,2}(\d)'),
        (match) => '${match.group(1)}${match.group(2)}',
      );
  for (final match in RegExp(r'[\d\s,.]{4,}').allMatches(normalized)) {
    final digits = match.group(0)!.replaceAll(RegExp(r'\D'), '');
    if (digits.length < 4 || digits.length > 7) continue;
    final value = int.tryParse(digits);
    if (value != null &&
        value > 0 &&
        value <= 9_999_999 &&
        value >= minimumKm) {
      yield value;
    }
  }
}

Map<String, Object?> _latencyJson(List<int> values) {
  if (values.isEmpty) return {'samples': 0};
  final sorted = [...values]..sort();
  int percentile(double value) => sorted[((sorted.length - 1) * value).round()];
  return {
    'samples': sorted.length,
    'median_ms': percentile(0.5) / 1000,
    'p95_ms': percentile(0.95) / 1000,
  };
}

Map<String, Object?> _object(Object? value, String label) {
  if (value is! Map<String, Object?>) {
    throw FormatException('$label must be a JSON object.');
  }
  return value;
}

String _requiredString(Map<String, Object?> json, String key) {
  final value = json[key];
  if (value is! String || value.trim().isEmpty) {
    throw FormatException('$key must be a non-empty string.');
  }
  return value;
}

OdometerScanMode _mode(String value) => switch (value) {
  'START' => OdometerScanMode.start,
  'END' => OdometerScanMode.end,
  _ => throw FormatException('Unsupported scan mode: $value.'),
};

OdometerOcrDecision _decision(String value) => switch (value) {
  'ACCEPTED' => OdometerOcrDecision.accepted,
  'NEEDS_REVIEW' => OdometerOcrDecision.needsReview,
  'NO_READING' => OdometerOcrDecision.noReading,
  _ => throw FormatException('Unsupported decision: $value.'),
};
