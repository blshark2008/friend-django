from rest_framework import serializers
from .models import Department, Position


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'name', 'code_1c', 'parent', 'is_active']


class PositionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ['id', 'name', 'code_1c', 'department', 'is_active']
