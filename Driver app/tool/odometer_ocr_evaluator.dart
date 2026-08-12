import 'dart:convert';
import 'dart:io';

import 'package:driver_app/core/odometer_ocr_evaluation.dart';

Future<void> main(List<String> arguments) async {
  final path = arguments.isEmpty
      ? 'test/fixtures/odometer_ocr/manifest.json'
      : arguments.single;
  final corpus = decodeOdometerCorpus(await File(path).readAsString());
  final report = evaluateOdometerCorpus(corpus, legacyTextBaseline);
  final parserReport = evaluateParserCorpus(corpus);
  final trainingReport = evaluateOdometerCorpus(
    corpusPartition(corpus, heldOut: false),
    parserScoringBaseline,
  );
  final heldOutReport = evaluateOdometerCorpus(
    corpusPartition(corpus, heldOut: true),
    parserScoringBaseline,
  );
  stdout.writeln(const JsonEncoder.withIndent('  ').convert(report.toJson()));
  stdout.writeln(
    const JsonEncoder.withIndent('  ').convert({
      'parser_only': parserReport.toJson(),
      'scoring_training': trainingReport.toJson(),
      'scoring_held_out': heldOutReport.toJson(),
    }),
  );
}
