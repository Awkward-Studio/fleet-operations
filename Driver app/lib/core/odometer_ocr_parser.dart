enum OdometerDecimalEvidence { none, tenths }

class OdometerOcrRect {
  const OdometerOcrRect({
    required this.left,
    required this.top,
    required this.right,
    required this.bottom,
  });

  final double left;
  final double top;
  final double right;
  final double bottom;

  double get width => right - left;
  double get height => bottom - top;

  OdometerOcrRect expandToInclude(OdometerOcrRect other) => OdometerOcrRect(
    left: left < other.left ? left : other.left,
    top: top < other.top ? top : other.top,
    right: right > other.right ? right : other.right,
    bottom: bottom > other.bottom ? bottom : other.bottom,
  );
}

class OdometerOcrElementInput {
  const OdometerOcrElementInput({required this.text, required this.bounds});

  final String text;
  final OdometerOcrRect bounds;
}

class OdometerOcrLineInput {
  const OdometerOcrLineInput({
    required this.text,
    this.elements = const [],
    this.bounds,
  });

  final String text;
  final List<OdometerOcrElementInput> elements;
  final OdometerOcrRect? bounds;
}

class OdometerOcrBlockInput {
  const OdometerOcrBlockInput({required this.lines});

  final List<OdometerOcrLineInput> lines;
}

class OdometerOcrDocumentInput {
  const OdometerOcrDocumentInput({required this.blocks, required this.variant});

  final List<OdometerOcrBlockInput> blocks;
  final String variant;
}

class OdometerGlyphSubstitution {
  const OdometerGlyphSubstitution({
    required this.offset,
    required this.source,
    required this.digit,
  });

  final int offset;
  final String source;
  final String digit;
}

class ParsedOdometerCandidate {
  const ParsedOdometerCandidate({
    required this.readingKm,
    required this.sourceText,
    required this.normalizedDigits,
    required this.separators,
    required this.hasDistanceUnit,
    required this.hasOdometerLabel,
    required this.decimalEvidence,
    required this.substitutions,
    required this.variant,
    required this.extractor,
    required this.blockIndex,
    required this.lineIndex,
    this.bounds,
  });

  final int readingKm;
  final String sourceText;
  final String normalizedDigits;
  final List<String> separators;
  final bool hasDistanceUnit;
  final bool hasOdometerLabel;
  final OdometerDecimalEvidence decimalEvidence;
  final List<OdometerGlyphSubstitution> substitutions;
  final String variant;
  final String extractor;
  final int blockIndex;
  final int lineIndex;
  final OdometerOcrRect? bounds;
}

class OdometerOcrParser {
  const OdometerOcrParser();

  static const _glyphs = <String, String>{
    'O': '0',
    'o': '0',
    'Q': '0',
    'q': '0',
    'D': '0',
    'I': '1',
    'i': '1',
    'l': '1',
    '|': '1',
    '!': '1',
    'S': '5',
    's': '5',
    'B': '8',
    'Z': '2',
    'z': '2',
  };

  List<ParsedOdometerCandidate> parse(OdometerOcrDocumentInput document) {
    final candidates = <ParsedOdometerCandidate>[];
    for (
      var blockIndex = 0;
      blockIndex < document.blocks.length;
      blockIndex++
    ) {
      final block = document.blocks[blockIndex];
      for (var lineIndex = 0; lineIndex < block.lines.length; lineIndex++) {
        final line = block.lines[lineIndex];
        final context = _LineContext(line.text);
        if (context.isCompetingDashboardValue) continue;

        if (line.elements.isNotEmpty) {
          candidates.addAll(
            _parseElementRuns(
              line,
              context,
              document.variant,
              blockIndex,
              lineIndex,
            ),
          );
        } else {
          candidates.addAll(
            _parseLineText(
              line,
              context,
              document.variant,
              blockIndex,
              lineIndex,
            ),
          );
        }
      }
    }
    return List.unmodifiable(candidates);
  }

  List<ParsedOdometerCandidate> _parseElementRuns(
    OdometerOcrLineInput line,
    _LineContext context,
    String variant,
    int blockIndex,
    int lineIndex,
  ) {
    final elements = [...line.elements]
      ..sort((a, b) => a.bounds.left.compareTo(b.bounds.left));
    final heights = elements.map((element) => element.bounds.height).toList()
      ..sort();
    final typicalHeight = heights[heights.length ~/ 2];
    final maximumGap = typicalHeight * 0.65;
    final runs = <List<OdometerOcrElementInput>>[];

    for (final element in elements) {
      if (!_isNumericFragment(element.text)) continue;
      if (runs.isEmpty ||
          element.bounds.left - runs.last.last.bounds.right > maximumGap) {
        runs.add([element]);
      } else {
        runs.last.add(element);
      }
    }

    return [
      for (final run in runs)
        ..._parseToken(
          run.map((element) => element.text.trim()).join(),
          context: context,
          variant: variant,
          blockIndex: blockIndex,
          lineIndex: lineIndex,
          bounds: run
              .map((element) => element.bounds)
              .reduce((value, next) => value.expandToInclude(next)),
          extractor: 'element-run',
        ),
    ];
  }

  List<ParsedOdometerCandidate> _parseLineText(
    OdometerOcrLineInput line,
    _LineContext context,
    String variant,
    int blockIndex,
    int lineIndex,
  ) {
    var searchable = line.text
        .replaceAll(RegExp(r'\b\d{1,2}:\d{2}(?::\d{2})?\b'), ' ')
        .replaceAll(RegExp(r'\b\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b'), ' ');
    final tokens = <String>[];

    final groupedSpaces = RegExp(r'(?<!\d)\d{1,3}(?:[ ]\d{3})+(?!\d)');
    searchable = searchable.replaceAllMapped(groupedSpaces, (match) {
      final prefix = searchable.substring(0, match.start);
      if (RegExp(r'\d\s+$').hasMatch(prefix)) return match.group(0)!;
      tokens.add(match.group(0)!);
      return ' ';
    });

    final tokenPattern = RegExp(
      r'(?<![A-Za-z0-9])[0-9OQDIil|!SBZoqsz][0-9OQDIil|!SBZoqsz,.]{0,14}(?![A-Za-z0-9])',
    );
    tokens.addAll(
      tokenPattern.allMatches(searchable).map((match) => match.group(0)!),
    );

    return [
      for (final token in tokens)
        ..._parseToken(
          token,
          context: context,
          variant: variant,
          blockIndex: blockIndex,
          lineIndex: lineIndex,
          bounds: line.bounds,
          extractor: 'line-token',
        ),
    ];
  }

  List<ParsedOdometerCandidate> _parseToken(
    String source, {
    required _LineContext context,
    required String variant,
    required int blockIndex,
    required int lineIndex,
    required OdometerOcrRect? bounds,
    required String extractor,
  }) {
    final hasRecognizedDigit = source.contains(RegExp(r'\d'));
    final lowerSource = source.toLowerCase();
    final isKnownLabel = const {
      'odo',
      'odometer',
      'total',
      'trip',
      'range',
      'speed',
    }.contains(lowerSource);
    if (!hasRecognizedDigit &&
        (isKnownLabel ||
            source.length < 4 ||
            (!context.hasOdometerLabel && !context.hasDistanceUnit))) {
      return const [];
    }
    final substitutions = <OdometerGlyphSubstitution>[];
    final normalized = StringBuffer();
    for (var index = 0; index < source.length; index++) {
      final character = source[index];
      final replacement = _glyphs[character];
      if (replacement != null) {
        substitutions.add(
          OdometerGlyphSubstitution(
            offset: index,
            source: character,
            digit: replacement,
          ),
        );
        normalized.write(replacement);
      } else {
        normalized.write(character);
      }
    }
    final valueText = normalized.toString();
    final separators = RegExp(
      r'[, .]',
    ).allMatches(source).map((match) => match.group(0)!).toList();
    var decimalEvidence = OdometerDecimalEvidence.none;
    late String digits;

    if (valueText.contains('.')) {
      final decimal = RegExp(r'^(\d{1,7})\.(\d)$').firstMatch(valueText);
      if (decimal == null) return const [];
      digits = decimal.group(1)!;
      decimalEvidence = OdometerDecimalEvidence.tenths;
    } else if (valueText.contains(',')) {
      if (!RegExp(r'^\d{1,3}(?:,\d{3})+$').hasMatch(valueText)) {
        return const [];
      }
      digits = valueText.replaceAll(',', '');
    } else if (valueText.contains(' ')) {
      if (!RegExp(r'^\d{1,3}(?: \d{3})+$').hasMatch(valueText)) {
        return const [];
      }
      digits = valueText.replaceAll(' ', '');
    } else {
      if (!RegExp(r'^\d{1,7}$').hasMatch(valueText)) return const [];
      digits = valueText;
    }

    if (digits.length > 7) return const [];
    final reading = int.tryParse(digits);
    if (reading == null || reading < 1 || reading > 9_999_999) return const [];

    return [
      ParsedOdometerCandidate(
        readingKm: reading,
        sourceText: source,
        normalizedDigits: digits,
        separators: List.unmodifiable(separators),
        hasDistanceUnit: context.hasDistanceUnit,
        hasOdometerLabel: context.hasOdometerLabel,
        decimalEvidence: decimalEvidence,
        substitutions: List.unmodifiable(substitutions),
        variant: variant,
        extractor: extractor,
        blockIndex: blockIndex,
        lineIndex: lineIndex,
        bounds: bounds,
      ),
    ];
  }

  bool _isNumericFragment(String text) {
    final compact = text.trim();
    if (compact.isEmpty) return false;
    if (compact.length > 15) return false;
    return RegExp(r'^[0-9OQDIil|!SBZoqsz,.]+$').hasMatch(compact) &&
        (compact.contains(RegExp(r'\d')) || compact.length >= 4);
  }
}

class _LineContext {
  _LineContext(String text) : lower = text.toLowerCase();

  final String lower;

  bool get hasOdometerLabel =>
      RegExp(r'\b(?:odo|odometer|total)\b').hasMatch(lower);

  bool get hasDistanceUnit =>
      RegExp(r'\bkm\b(?!\s*/\s*h)|\bmi(?:les?)?\b').hasMatch(lower);

  bool get isCompetingDashboardValue =>
      RegExp(
        r'\bkm\s*/\s*h\b|\bmph\b|\bl\s*/\s*100\s*km\b|\bmpg\b',
      ).hasMatch(lower) ||
      (RegExp(r'\b(?:range|speed|average|avg|fuel)\b').hasMatch(lower) &&
          !hasOdometerLabel);
}
