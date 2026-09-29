from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Company, CompanyMember


class PartnersTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="owner", password="StrongPass123!")
        self.member = get_user_model().objects.create_user(username="member", password="StrongPass123!")
        self.outsider = get_user_model().objects.create_user(username="outsider", password="StrongPass123!")
        self.client = APIClient()

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def create_company(self):
        self.as_user(self.owner)
        response = self.client.post("/api/partners/companies/", {
            "name": "Silk Road Logistics", "phone_number": "+998901234567",
            "email": "office@example.com", "address": "Toshkent",
        })
        self.assertEqual(response.status_code, 201)
        return response.data["id"]

    def test_company_crud_and_owner_membership(self):
        self.assertEqual(self.client.get("/api/partners/companies/").status_code, 401)
        company_id = self.create_company()
        company_url = f"/api/partners/companies/{company_id}/"
        membership = CompanyMember.objects.get(company_id=company_id, user=self.owner)
        self.assertEqual(membership.role, CompanyMember.Role.OWNER)
        self.assertTrue(membership.can_post_cargo)
        self.assertEqual(self.client.get("/api/partners/companies/").status_code, 200)
        self.assertEqual(self.client.get(company_url).status_code, 200)
        self.as_user(self.outsider)
        self.assertEqual(self.client.patch(company_url, {"name": "Fake"}).status_code, 403)
        self.assertEqual(self.client.delete(company_url).status_code, 403)
        self.as_user(self.owner)
        self.assertEqual(self.client.put(company_url, {"name": "New Name", "phone_number": "+998911112233"}).status_code, 200)
        self.assertEqual(self.client.patch(company_url, {"address": "Samarqand"}).status_code, 200)
        self.assertEqual(self.client.delete(company_url).status_code, 204)
        self.assertFalse(Company.objects.filter(pk=company_id).exists())

    def test_membership_crud_permissions_and_last_owner(self):
        company_id = self.create_company()
        members_url = f"/api/partners/companies/{company_id}/members/"
        owner_member = CompanyMember.objects.get(company_id=company_id, user=self.owner)
        self.as_user(self.outsider)
        self.assertEqual(self.client.get(members_url).status_code, 403)
        self.assertEqual(self.client.post(members_url, {"username": "outsider"}).status_code, 403)
        self.as_user(self.owner)
        added = self.client.post(members_url, {"username": "member", "role": "member", "can_post_cargo": True})
        self.assertEqual(added.status_code, 201)
        self.assertEqual(added.data["user_username"], "member")
        member_url = f"{members_url}{added.data['id']}/"
        self.assertEqual(self.client.post(members_url, {"username": "member"}).status_code, 400)
        self.assertEqual(self.client.get(members_url).status_code, 200)
        self.assertEqual(self.client.get(member_url).status_code, 200)
        self.as_user(self.member)
        self.assertEqual(self.client.get(members_url).status_code, 200)
        self.assertEqual(self.client.patch(member_url, {"role": "owner"}).status_code, 403)
        self.as_user(self.owner)
        owner_url = f"{members_url}{owner_member.id}/"
        self.assertEqual(self.client.delete(owner_url).status_code, 400)
        self.assertEqual(self.client.patch(owner_url, {"role": "member"}).status_code, 400)
        self.assertEqual(self.client.put(member_url, {"role": "owner", "can_post_cargo": True}).status_code, 200)
        self.assertEqual(self.client.patch(owner_url, {"role": "member"}).status_code, 200)
        self.assertEqual(self.client.delete(owner_url).status_code, 403)
        self.as_user(self.member)
        self.assertEqual(self.client.delete(owner_url).status_code, 204)
        self.assertEqual(self.client.patch(member_url, {"can_post_cargo": False}).status_code, 200)

    def test_nested_member_cannot_be_accessed_from_other_company(self):
        first_id = self.create_company()
        second_id = self.create_company()
        member = CompanyMember.objects.get(company_id=first_id, user=self.owner)
        response = self.client.get(f"/api/partners/companies/{second_id}/members/{member.pk}/")
        self.assertEqual(response.status_code, 404)
