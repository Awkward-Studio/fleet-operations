import 'package:driver_app/main.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('shows the driver login screen', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const DriverApp());
    await tester.pump();

    expect(find.text('Start your shift'), findsOneWidget);
    expect(find.text('Username or email'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
  });
}
