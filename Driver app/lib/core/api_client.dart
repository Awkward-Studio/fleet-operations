import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:shared_preferences/shared_preferences.dart';

const String apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://10.0.2.2:8000',
);

class ServerUrlStore {
  static const _key = 'driver_app_server_url';

  static Future<String> get baseUrl async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_key);
    if (apiBaseUrl != 'http://10.0.2.2:8000' && (stored == null || stored == 'http://10.0.2.2:8000')) {
      return _cleanUrl(apiBaseUrl);
    }
    if (stored != null && stored.trim().isNotEmpty) {
      return _cleanUrl(stored);
    }
    return _cleanUrl(apiBaseUrl);
  }

  static Future<void> save(String rawUrl) async {
    final prefs = await SharedPreferences.getInstance();
    final cleaned = _cleanUrl(rawUrl);
    await prefs.setString(_key, cleaned);
  }

  static String _cleanUrl(String raw) {
    var cleaned = raw.trim();
    if (cleaned.contains('.local')) {
      cleaned = cleaned.replaceAll('.local', '');
    }
    if (!cleaned.startsWith('http://') && !cleaned.startsWith('https://')) {
      cleaned = 'http://$cleaned';
    }
    while (cleaned.endsWith('/')) {
      cleaned = cleaned.substring(0, cleaned.length - 1);
    }
    return cleaned;
  }
}

class ApiClient {
  Future<Uri> _uri(String path) async {
    final base = await ServerUrlStore.baseUrl;
    return Uri.parse('$base/api$path');
  }

  Future<void> login(String username, String password) async {
    final uri = await _uri('/auth/login/');
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'username': username, 'password': password}),
    );

    final data = decode(response) as Map<String, dynamic>;
    await TokenStore.save(
      access: data['access'] as String,
      refresh: data['refresh'] as String,
    );
  }

  Future<dynamic> get(String path) async {
    return decode(await _authorizedGet(path));
  }

  Future<dynamic> post(String path, Map<String, dynamic> payload) async {
    return decode(await _authorizedPost(path, payload));
  }

  Future<dynamic> postMultipart(
    String path, {
    required Map<String, String> fields,
    required String fileField,
    required File file,
    String contentType = 'image/jpeg',
  }) async {
    return decode(
      await _authorizedMultipartPost(
        path,
        fields: fields,
        fileField: fileField,
        file: file,
        contentType: contentType,
      ),
    );
  }

  Future<dynamic> postMultipartFiles(
    String path, {
    required Map<String, String> fields,
    required List<File> files,
    required String fileField,
    String contentType = 'image/jpeg',
  }) async {
    final token = await TokenStore.accessToken;
    final request = http.MultipartRequest('POST', _uri(path))
      ..fields.addAll(fields);

    for (final file in files) {
      request.files.add(
        await http.MultipartFile.fromPath(
          fileField,
          file.path,
          contentType: MediaType.parse(contentType),
        ),
      );
    }

    if (token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }

    var streamed = await request.send();
    var response = await http.Response.fromStream(streamed);

    if (response.statusCode == 401 && await _refreshToken()) {
      final nextToken = await TokenStore.accessToken;
      final retry = http.MultipartRequest('POST', _uri(path))
        ..fields.addAll(fields);

      for (final file in files) {
        retry.files.add(
          await http.MultipartFile.fromPath(
            fileField,
            file.path,
            contentType: MediaType.parse(contentType),
          ),
        );
      }

      if (nextToken != null) {
        retry.headers['Authorization'] = 'Bearer $nextToken';
      }
      streamed = await retry.send();
      response = await http.Response.fromStream(streamed);
    }

    return decode(response);
  }

  Future<http.Response> _authorizedGet(String path) async {
    final token = await TokenStore.accessToken;
    final uri = await _uri(path);
    final response = await http.get(
      uri,
      headers: {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 401 && await _refreshToken()) {
      final nextToken = await TokenStore.accessToken;
      final retryUri = await _uri(path);
      return http.get(
        retryUri,
        headers: {
          'Content-Type': 'application/json',
          if (nextToken != null) 'Authorization': 'Bearer $nextToken',
        },
      );
    }

    return response;
  }

  Future<http.Response> _authorizedPost(
    String path,
    Map<String, dynamic> payload,
  ) async {
    final token = await TokenStore.accessToken;
    final uri = await _uri(path);
    final response = await http.post(
      uri,
      headers: {
        'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      },
      body: jsonEncode(payload),
    );

    if (response.statusCode == 401 && await _refreshToken()) {
      final nextToken = await TokenStore.accessToken;
      final retryUri = await _uri(path);
      return http.post(
        retryUri,
        headers: {
          'Content-Type': 'application/json',
          if (nextToken != null) 'Authorization': 'Bearer $nextToken',
        },
        body: jsonEncode(payload),
      );
    }

    return response;
  }

  Future<http.Response> _authorizedMultipartPost(
    String path, {
    required Map<String, String> fields,
    required String fileField,
    required File file,
    required String contentType,
  }) async {
    final token = await TokenStore.accessToken;
    final uri = await _uri(path);
    final request = http.MultipartRequest('POST', uri)
      ..fields.addAll(fields)
      ..files.add(
        await http.MultipartFile.fromPath(
          fileField,
          file.path,
          contentType: MediaType.parse(contentType),
        ),
      );
    if (token != null) {
      request.headers['Authorization'] = 'Bearer $token';
    }

    var streamed = await request.send();
    var response = await http.Response.fromStream(streamed);
    if (response.statusCode == 401 && await _refreshToken()) {
      final nextToken = await TokenStore.accessToken;
      final retryUri = await _uri(path);
      final retry = http.MultipartRequest('POST', retryUri)
        ..fields.addAll(fields)
        ..files.add(
          await http.MultipartFile.fromPath(
            fileField,
            file.path,
            contentType: MediaType.parse(contentType),
          ),
        );
      if (nextToken != null) {
        retry.headers['Authorization'] = 'Bearer $nextToken';
      }
      streamed = await retry.send();
      response = await http.Response.fromStream(streamed);
    }

    return response;
  }

  Future<bool> _refreshToken() async {
    final refreshToken = await TokenStore.refreshToken;
    if (refreshToken == null) return false;

    final uri = await _uri('/auth/token/refresh/');
    final response = await http.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh': refreshToken}),
    );

    if (response.statusCode >= 200 && response.statusCode < 300) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      await TokenStore.save(
        access: data['access'] as String,
        refresh: data['refresh'] as String? ?? refreshToken,
      );
      return true;
    }

    await TokenStore.clear();
    return false;
  }

  static dynamic decode(http.Response response) {
    final body = response.body.isEmpty ? null : jsonDecode(response.body);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return body;
    }

    if (body is Map<String, dynamic>) {
      throw Exception(
        body['detail'] ?? body['message'] ?? body.values.join(' '),
      );
    }
    throw Exception('Request failed with status ${response.statusCode}');
  }
}

class TokenStore {
  static const _accessKey = 'accessToken';
  static const _refreshKey = 'refreshToken';

  static Future<String?> get accessToken async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_accessKey);
  }

  static Future<String?> get refreshToken async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_refreshKey);
  }

  static Future<void> save({
    required String access,
    required String refresh,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_accessKey, access);
    await prefs.setString(_refreshKey, refresh);
  }

  static Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_accessKey);
    await prefs.remove(_refreshKey);
  }
}
