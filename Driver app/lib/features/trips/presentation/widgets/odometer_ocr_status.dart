import 'package:flutter/material.dart';

class OdometerOcrStatus extends StatelessWidget {
  const OdometerOcrStatus({
    super.key,
    required this.scanning,
    required this.message,
    this.isError = false,
  });

  final bool scanning;
  final String? message;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    if (!scanning && message == null) return const SizedBox.shrink();

    final color = scanning
        ? const Color(0xff1d4ed8)
        : isError
            ? const Color(0xff92400e)
            : const Color(0xff0f766e);
    final background = scanning
        ? const Color(0xffeff6ff)
        : isError
            ? const Color(0xfffff7ed)
            : const Color(0xffe8f3ef);
    final border = scanning
        ? const Color(0xffbfdbfe)
        : isError
            ? const Color(0xffffedd5)
            : const Color(0xffb7d8cb);

    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: background,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: border),
      ),
      child: Row(
        children: [
          scanning
              ? SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(color),
                  ),
                )
              : Icon(
                  isError
                      ? Icons.warning_amber_outlined
                      : Icons.document_scanner_outlined,
                  color: color,
                  size: 20,
                ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              scanning ? 'Reading odometer from photo...' : message!,
              style: TextStyle(color: color, fontWeight: FontWeight.w800),
            ),
          ),
        ],
      ),
    );
  }
}
