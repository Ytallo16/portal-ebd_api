from core.scoping import (
    get_org_child_ids,
    get_teaching_class_ids,
    is_campo_organization,
    is_somente_professor,
)
from core.tenant import get_operational_organization, get_user_organization


class OrganizationScopedViewMixin:
    use_operational_organization = False

    def get_active_organization(self):
        if self.use_operational_organization:
            return get_operational_organization(self.request)
        return get_user_organization(self.request)

    def get_teaching_class_filter(self, organization):
        if not is_somente_professor(self.request.user, organization):
            return None
        class_ids = get_teaching_class_ids(self.request.user, organization)
        return class_ids


class DashboardOrganizationMixin:
    def get_dashboard_organization_ids(self):
        org = get_user_organization(self.request)
        if is_campo_organization(org):
            return get_org_child_ids(org) or [org.id]
        return [org.id]
