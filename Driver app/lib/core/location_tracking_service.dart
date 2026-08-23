import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../features/trips/domain/trip.dart';
import 'api_client.dart';

const _trackingTripIdKey = 'activeLocationTrackingTripId';
const _trackingLastLatitudeKey = 'activeLocationTrackingLastLatitude';
const _trackingLastLongitudeKey = 'activeLocationTrackingLastLongitude';
const _trackingLastTimeKey = 'activeLocationTrackingLastTime';
const _trackingPollInterval = Duration(seconds: 30);

class _CurrentTripLookup {
  const _CurrentTripLookup({required this.succeeded, this.trip});

  final bool succeeded;
  final Map<String, dynamic>? trip;
}

class LocationTrackingService {
  const LocationTrackingService._();

  static Future<void> initialize() async {
    final service = FlutterBackgroundService();

    if (Platform.isAndroid) {
      final flutterLocalNotificationsPlugin = FlutterLocalNotificationsPlugin();
      const AndroidInitializationSettings initializationSettingsAndroid =
          AndroidInitializationSettings('@mipmap/ic_launcher');
      const InitializationSettings initializationSettings =
          InitializationSettings(android: initializationSettingsAndroid);
      await flutterLocalNotificationsPlugin.initialize(
        settings: initializationSettings,
      );

      const AndroidNotificationChannel channel = AndroidNotificationChannel(
        'driver_location_tracking',
        'Live GPS Tracking',
        description: 'Used for streaming live location during active trips.',
        importance: Importance.low,
      );

      await flutterLocalNotificationsPlugin
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >()
          ?.createNotificationChannel(channel);

      await flutterLocalNotificationsPlugin
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >()
          ?.requestNotificationsPermission();
    }

    await service.configure(
      androidConfiguration: AndroidConfiguration(
        onStart: locationTrackingServiceEntryPoint,
        autoStart: false,
        isForegroundMode: true,
        notificationChannelId: 'driver_location_tracking',
        initialNotificationTitle: 'Live GPS Tracking Active',
        initialNotificationContent: 'Streaming active trip location',
        foregroundServiceNotificationId: 907,
        foregroundServiceTypes: [AndroidForegroundType.location],
      ),
      iosConfiguration: IosConfiguration(
        autoStart: false,
        onForeground: locationTrackingServiceEntryPoint,
        onBackground: iosLocationTrackingBackground,
      ),
    );
  }

  static Future<bool> ensureTrackingForActiveTrip(
    BuildContext context,
    Trip? trip,
  ) async {
    if (trip?.status != TripStatus.active) {
      await stop();
      return false;
    }

    final hasPermission = await _ensureLocationPermission(context);
    if (!hasPermission) return false;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_trackingTripIdKey, trip!.id);

    try {
      final service = FlutterBackgroundService();
      if (!await service.isRunning()) {
        await service.startService();
      } else {
        service.invoke('setTrip', {'trip_id': trip.id});
      }
    } catch (e) {
      debugPrint('Location tracking service start failed: $e');
    }

    return true;
  }

  static Future<void> startAfterOtpSuccess(Trip trip) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_trackingTripIdKey, trip.id);
    try {
      final service = FlutterBackgroundService();
      if (!await service.isRunning()) {
        await service.startService();
      } else {
        service.invoke('setTrip', {'trip_id': trip.id});
      }
    } catch (e) {
      debugPrint('Location tracking service start after OTP failed: $e');
    }
  }

  static Future<void> stop() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_trackingTripIdKey);
    await prefs.remove(_trackingLastLatitudeKey);
    await prefs.remove(_trackingLastLongitudeKey);
    await prefs.remove(_trackingLastTimeKey);
    if (!Platform.isAndroid && !Platform.isIOS) return;
    try {
      final service = FlutterBackgroundService();
      if (await service.isRunning()) {
        service.invoke('stopTracking');
      }
    } catch (error) {
      debugPrint('Location tracking service stop failed: $error');
    }
  }

  static Future<bool> _ensureLocationPermission(BuildContext context) async {
    final enabled = await Geolocator.isLocationServiceEnabled();
    if (!enabled) {
      if (context.mounted) {
        await _showRationale(
          context,
          'Location services are off',
          'Turn on device location so dispatch can track the active ride.',
        );
      }
      return false;
    }

    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied && context.mounted) {
      final proceed = await _showRationale(
        context,
        'Allow ride tracking',
        'Fleet Operations needs location while you are on an active ride so dispatch can see live trip progress.',
      );
      if (!proceed) return false;
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.whileInUse && context.mounted) {
      await _showRationale(
        context,
        'Background tracking',
        'For locked-screen or background tracking, set location permission to Always for this driver app.',
      );
      permission = await Geolocator.requestPermission();
    }

    return permission == LocationPermission.always ||
        permission == LocationPermission.whileInUse;
  }

  static Future<bool> _showRationale(
    BuildContext context,
    String title,
    String message,
  ) async {
    final result = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Not now'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Continue'),
          ),
        ],
      ),
    );
    return result ?? false;
  }
}

@pragma('vm:entry-point')
Future<bool> iosLocationTrackingBackground(ServiceInstance service) async {
  WidgetsFlutterBinding.ensureInitialized();
  DartPluginRegistrant.ensureInitialized();
  return true;
}

@pragma('vm:entry-point')
void locationTrackingServiceEntryPoint(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();

  if (service is AndroidServiceInstance) {
    service.on('setAsForeground').listen((_) {
      service.setAsForegroundService();
    });
  }

  service.on('setTrip').listen((event) async {
    final tripId = event?['trip_id'];
    if (tripId is int) {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setInt(_trackingTripIdKey, tripId);
    }
  });

  service.on('stopTracking').listen((_) async {
    await _clearTrackingPrefs();
    service.stopSelf();
  });

  var pollInFlight = false;
  Timer.periodic(_trackingPollInterval, (timer) async {
    if (pollInFlight) return;
    pollInFlight = true;

    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.reload();
      final tripId = prefs.getInt(_trackingTripIdKey);
      if (tripId == null) {
        timer.cancel();
        await service.stopSelf();
        return;
      }

      final currentTrip = await _loadCurrentTrip();
      if (currentTrip.succeeded &&
          !_isActiveMatchingTrip(currentTrip.trip, tripId)) {
        timer.cancel();
        await _clearTrackingPrefs();
        await service.stopSelf();
        return;
      }

      if (service is AndroidServiceInstance &&
          await service.isForegroundService()) {
        service.setForegroundNotificationInfo(
          title: 'Live GPS Tracking Active',
          content: 'Streaming trip #$tripId location to dispatch',
        );
      }

      final position = await _readPosition();
      if (position == null) return;

      final shouldPost = await _shouldPostPosition(prefs, position);
      if (!shouldPost) return;

      final posted = await _postLocation(tripId, position);
      if (posted) {
        await prefs.setDouble(_trackingLastLatitudeKey, position.latitude);
        await prefs.setDouble(_trackingLastLongitudeKey, position.longitude);
        await prefs.setInt(
          _trackingLastTimeKey,
          DateTime.now().millisecondsSinceEpoch,
        );
        service.invoke('trackingUpdate', {
          'trip_id': tripId,
          'timestamp': DateTime.now().toIso8601String(),
        });
      }
    } finally {
      pollInFlight = false;
    }
  });
}

Future<_CurrentTripLookup> _loadCurrentTrip() async {
  final token = await _accessToken();
  if (token == null) return const _CurrentTripLookup(succeeded: true);

  try {
    final base = await ServerUrlStore.baseUrl;
    final response = await http.get(
      Uri.parse('$base/api/fleet/driver/my-trips/current/'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      return const _CurrentTripLookup(succeeded: false);
    }
    if (response.body.isEmpty || response.body == 'null') {
      return const _CurrentTripLookup(succeeded: true);
    }
    return _CurrentTripLookup(
      succeeded: true,
      trip: jsonDecode(response.body) as Map<String, dynamic>,
    );
  } catch (_) {
    return const _CurrentTripLookup(succeeded: false);
  }
}

bool _isActiveMatchingTrip(Map<String, dynamic>? trip, int tripId) {
  return trip?['id'] == tripId && trip?['status'] == 'active';
}

Future<Position?> _readPosition() async {
  try {
    final permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      return null;
    }

    try {
      final current = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.medium,
          timeLimit: Duration(seconds: 5),
        ),
      );
      return current;
    } catch (_) {
      // Timeout or background GPS delay
    }

    return await Geolocator.getLastKnownPosition();
  } catch (_) {
    return null;
  }
}

Future<bool> _shouldPostPosition(
  SharedPreferences prefs,
  Position position,
) async {
  final lastTimeMs = prefs.getInt(_trackingLastTimeKey) ?? 0;
  final nowMs = DateTime.now().millisecondsSinceEpoch;
  final elapsedMs = nowMs - lastTimeMs;

  // Strict rate-limit guard: never post faster than 25s apart
  if (lastTimeMs > 0 && elapsedMs < 25000) {
    return false;
  }

  final lastLat = prefs.getDouble(_trackingLastLatitudeKey);
  final lastLng = prefs.getDouble(_trackingLastLongitudeKey);
  if (lastLat == null || lastLng == null) return true;

  final meters = Geolocator.distanceBetween(
    lastLat,
    lastLng,
    position.latitude,
    position.longitude,
  );

  return meters >= 5 || elapsedMs >= 30000;
}

Future<bool> _postLocation(int tripId, Position position) async {
  final token = await _accessToken();
  if (token == null) return false;

  final lat = double.parse(position.latitude.toStringAsFixed(6));
  final lng = double.parse(position.longitude.toStringAsFixed(6));
  final speed =
      (position.speed.isNaN || position.speed.isInfinite || position.speed < 0)
      ? 0.0
      : double.parse((position.speed * 3.6).toStringAsFixed(2));
  final heading = (position.heading.isNaN || position.heading.isInfinite)
      ? 0.0
      : double.parse(position.heading.toStringAsFixed(2));

  try {
    final base = await ServerUrlStore.baseUrl;
    final response = await http.post(
      Uri.parse('$base/api/fleet/trips/$tripId/location/'),
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $token',
      },
      body: jsonEncode({
        'latitude': lat,
        'longitude': lng,
        'speed_kmh': speed,
        'heading': heading,
        'timestamp': DateTime.now().toUtc().toIso8601String(),
      }),
    );
    return response.statusCode >= 200 && response.statusCode < 300;
  } catch (_) {
    return false;
  }
}

Future<String?> _accessToken() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.reload();
  return prefs.getString('accessToken');
}

Future<void> _clearTrackingPrefs() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove(_trackingTripIdKey);
  await prefs.remove(_trackingLastLatitudeKey);
  await prefs.remove(_trackingLastLongitudeKey);
  await prefs.remove(_trackingLastTimeKey);
}
