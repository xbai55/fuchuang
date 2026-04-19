import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:anti_fraud_app/main.dart';

void main() {
  testWidgets('AntiFraudApp renders core mobile flows',
      (WidgetTester tester) async {
    await tester.pumpWidget(const AntiFraudApp(bypassAuth: true));
    await tester.pump();

    expect(find.text('天枢明御'), findsWidgets);
    expect(find.text('快速检测'), findsOneWidget);
    expect(find.text('智能检测'), findsOneWidget);

    await tester.tap(find.text('反诈助手'));
    await tester.pump();

    expect(find.text('有疑问，先问清楚'), findsOneWidget);

    await tester.tap(find.text('历史记录'));
    await tester.pump();

    expect(find.text('历史记录'), findsWidgets);
  });

  testWidgets('send button starts detection from home input',
      (WidgetTester tester) async {
    await tester.pumpWidget(const AntiFraudApp(bypassAuth: true));
    await tester.pump();

    await tester.enterText(find.byType(EditableText).first, '可疑客服要求先转账');
    await tester.tap(find.byKey(const ValueKey('send-detection-button')));
    await tester.pump();

    expect(tester.takeException(), isNull);
  });
}
