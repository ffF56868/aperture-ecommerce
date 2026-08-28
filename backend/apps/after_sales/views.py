"""Read-only API endpoints for after-sales rules."""

from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .policies import AFTER_SALES_POLICIES, get_policy
from .serializers import AfterSalesPolicySerializer


@extend_schema(
    summary="获取售后规则列表",
    tags=["售后 Agent"],
    responses=AfterSalesPolicySerializer(many=True),
)
class AfterSalesPolicyListView(APIView):
    """Return safe, static business rules used by the later Agent workflow."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        serializer = AfterSalesPolicySerializer(AFTER_SALES_POLICIES, many=True)
        return Response(serializer.data)


@extend_schema(
    summary="获取一条售后规则",
    tags=["售后 Agent"],
    responses=AfterSalesPolicySerializer,
)
class AfterSalesPolicyDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, policy_key, *args, **kwargs):
        policy = get_policy(policy_key)
        if policy is None:
            raise NotFound("未找到对应的售后规则。")
        return Response(AfterSalesPolicySerializer(policy).data)
