from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    permissions = serializers.ReadOnlyField(source="permissions_list")

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "permissions"]
        read_only_fields = ["id", "permissions"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(write_only=True, required=True, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "confirm_password", "first_name", "last_name", "role"]
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": True},
            "last_name": {"required": False, "allow_blank": True},
            "role": {"required": False},
        }

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value.lower()

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        
        if len(data["password"]) < 6:
            raise serializers.ValidationError({"password": "Password must be at least 6 characters long."})

        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        role = validated_data.pop("role", "admin")
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            role=role,
        )
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_new_password = serializers.CharField(required=True, write_only=True)

    def validate(self, data):
        user = self.context["request"].user
        if not user.check_password(data["old_password"]):
            raise serializers.ValidationError({"old_password": "Old password is incorrect."})

        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError({"confirm_new_password": "New passwords do not match."})
        
        if len(data["new_password"]) < 6:
            raise serializers.ValidationError({"new_password": "New password must be at least 6 characters long."})

        if data["old_password"] == data["new_password"]:
            raise serializers.ValidationError({"new_password": "New password must be different from old password."})

        return data
