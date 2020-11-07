"""
Inventory API Service Test Suite
Test cases can be run with the following:
"""
import os
import logging
from unittest import TestCase
from unittest.mock import MagicMock, patch

from werkzeug import test
from werkzeug.wrappers import Response
from flask_api import status  # HTTP Status Codes
from service import app, service
from service.service import app, init_db, set_permissions
from service.model import Inventory, DataValidationError, DB
from .inventory_factory import InventoryFactory

DATABASE_URI = os.getenv("DATABASE_URI", "postgres://postgres:postgres@localhost:5432/postgres")

PERMS = [True, False]
BASE = service.PERMISSION

class InventoryAPITest(TestCase):
    """ Inventory Services Tests """

    @classmethod
    def setUpClass(cls):
        """ Run once before all tests """
        app.debug = False
        app.testing = True
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        init_db()

    @classmethod
    def tearDownClass(cls):
        """ Run once after all tests """
        DB.session.close()

    def setUp(self):
        """ Runs before each test """
        DB.drop_all()  # clean up the last tests
        DB.create_all()  # create new tables
        self.app = app.test_client()

    def tearDown(self):
        DB.session.remove()
        DB.drop_all()

######################################################################
#  T E S T   C A S E S
######################################################################

    def test_405(self):
        """Testing 405 error"""
        service.method_not_supported("Testing 405")

    def test_500(self):
        """Testing 500 error"""
        service.internal_server_error("Testing 500")

    def test_409(self):
        """Testing 409 error"""
        service.create_conflict_error("Testing 409")

    def test_db(self):
        """Testing DB error"""
        service.db_connection_error("Testing DB error")

    def test_wrong_content_type(self):
        """trigger wrong content type error"""
        set_permissions(BASE)
        test_inventory = InventoryFactory()
        resp = self.app.post("/inventory", json=test_inventory.serialize(), content_type="text")
        self.assertEqual(resp.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    @patch('service.service.create_inventory')
    def test_bad_request(self, bad_request_mock):
        """ Bad Request error from Create Inventory """
        bad_request_mock.side_effect = DataValidationError()
        resp = self.app.post('/inventory', json="",
                             content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('service.service.create_inventory')
    def create_conflict_error(self, conflict_mock):
        """ Conflict Error from Create Inventory """
        conflict_mock.side_effect = DataValidationError()
        resp = self.app.post('/inventory', json="",
                             content_type='application/json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_index(self):
        """ Test the Home Page """
        resp = self.app.get("/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.get_json()
        self.assertEqual(data["name"], service.DEMO_MSG)

    def _create_inventories(self, count):
        """ Factory method to create inventory products in bulk """
        inventories = []
        global BASE
        set_permissions(BASE)
        for _ in range(count):
            test_inventory = InventoryFactory()
            resp = self.app.post(
                "/inventory", json=test_inventory.serialize(), content_type="application/json"
            )
            if BASE:
                self.assertEqual(
                    resp.status_code, status.HTTP_201_CREATED, "Created inventory record"
                )
                new_inventory = resp.get_json()
                test_inventory.product_id = new_inventory["product_id"]
                inventories.append(test_inventory)
            else:
                self.assertEqual(
                    resp.status_code, status.HTTP_400_BAD_REQUEST,
                )
        return inventories

    def test_permission(self):
        """ Sets PERMISSION """
        global PERMS
        for p in PERMS:
            set_permissions(p)

    ##################################################################
    # Testing POST
    def test_create_inventory(self):
        """ Create a new inventory """
        set_permissions(BASE)
        test_inventory = InventoryFactory()
        resp = self.app.post(
            "/inventory", json=test_inventory.serialize(), content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # Make sure location header is set
        location = resp.headers.get("Location", None)
        self.assertTrue(location != None)

        # Check the data is correct
        new_inventory = resp.get_json()
        self.assertTrue(new_inventory != None)
        self.assertEqual(new_inventory["product_id"],
            test_inventory.serialize()['product_id'], "Product ID does not match")
        self.assertEqual(new_inventory["quantity"],
            test_inventory.serialize()['quantity'], "Quantity does not match")
        self.assertEqual(new_inventory["restock_level"],
            test_inventory.serialize()['restock_level'], "Restock level does not match")
        self.assertEqual(new_inventory["available"],
            test_inventory.serialize()['available'], "Availability does not match")
        self.assertEqual(new_inventory["condition"],
            test_inventory.serialize()['condition'], "Conditions do not match")

        # Check that the location header was correct
        resp = self.app.get(location, content_type="application/json")
        if new_inventory["available"]==1 or service.PERMISSION:
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            new_inventory = resp.get_json()[0]
            self.assertTrue(new_inventory != None)
            self.assertEqual(new_inventory["product_id"],
                test_inventory.serialize()['product_id'], "Product ID does not match")
            self.assertEqual(new_inventory["quantity"],
                test_inventory.serialize()['quantity'], "Quantity does not match")
            self.assertEqual(new_inventory["restock_level"],
                test_inventory.serialize()['restock_level'], "Restock level does not match")
            self.assertEqual(new_inventory["available"],
                test_inventory.serialize()['available'], "Availability does not match")
            self.assertEqual(new_inventory["condition"],
                test_inventory.serialize()['condition'], "Conditions do not match")
        else:
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_inventory_bad_req(self):
        """ Create a new inventory WITHOUT condition """
        set_permissions(BASE)
        test_inventory = InventoryFactory()
        json = test_inventory.serialize()
        json.pop('condition')
        resp = self.app.post(
            "/inventory", json=json, content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_inventory_dup(self):
        """ Create a DUPLICATE inventory record """
        set_permissions(BASE)
        test_inventory = InventoryFactory()
        json = test_inventory.serialize()
        resp = self.app.post(
            "/inventory", json=json, content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        resp = self.app.post(
            "/inventory", json=json, content_type="application/json"
        )
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT)

    ##################################################################
    # Testing GET
    def test_list_inventory(self):
        """Get the entire inventory list"""
        global PERMS
        N = 10
        inventories = self._create_inventories(N)
        for p in PERMS:
            set_permissions(p)
            resp = self.app.get("/inventory")
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_inventory_not_found(self):
        """Get the entire inventory list"""
        global PERMS
        N = 10
        for p in PERMS:
            set_permissions(p)
            resp = self.app.get("/inventory")
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_inventory_not_found(self):
        """Get a product inventory that's not available"""
        resp = self.app.get("/inventory?product_id=0")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_inventory_by_pid(self):
        """Get inventory details by [product_id]"""
        global PERMS
        N = 10
        inventories = self._create_inventories(N)
        for inv in inventories:
            test_pid = inv.product_id
            for p in PERMS:
                set_permissions(p)
                resp = self.app.get("/inventory?product_id={}".format(test_pid), content_type="application/json")
                if inv.available == 1:
                    self.assertEqual(resp.status_code, status.HTTP_200_OK)
                else:
                    self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_inventory_by_pid_2(self):
        """Get inventory details by [product_id]"""
        global PERMS
        test_inventory = self._create_inventories(1)[0]
        pid = test_inventory.product_id
        for p in PERMS:
            set_permissions(p)
            resp = self.app.get("/inventory?product_id={}".format(pid+3), content_type="application/json")
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_inventory_by_pid_condition(self):
        """Get inventory details by [product_id, condition]"""
        test_inventory = self._create_inventories(1)[0]
        pid = test_inventory.product_id
        cnd = test_inventory.condition
        resp = self.app.get("/inventory/{}/condition/{}".format(pid, cnd),\
                            content_type="application/json")
        if test_inventory.available==1 or service.PERMISSION:
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
            data = resp.get_json()[0]
            self.assertEqual(data["product_id"], pid)
            self.assertEqual(data["condition"], cnd)
        else:
            self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_inventory_by_pid_condition_404(self):
        """Get inventory details by [product_id, condition] 404"""
        test_inventory = self._create_inventories(1)[0]
        resp = self.app.get("/inventory/{}/condition/{}".format(999, "new"),\
                            content_type="application/json")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    ##################################################################
    # Testing DELETE
    def test_delete_inventory(self):
        """Delete a product from the inventory"""
        global PERMS
        test_inventory = self._create_inventories(1)[0]
        for p in PERMS:
            set_permissions(p)
            resp = self.app.delete(
                "/inventory/{}/condition/{}".format(test_inventory.product_id, test_inventory.condition), content_type="application/json"
            )
            if p:
                self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
            else:
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    ##################################################################
    # Testing PUT
    def test_update_inventory(self):
        """Update an existing product in Inventory - 1"""
        global PERMS
        for p in PERMS:
            set_permissions(p)
            test_inventory = InventoryFactory()
            resp = self.app.post(
                "/inventory", json=test_inventory.serialize(), content_type="application/json"
            )
            if p:
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

                qty = 30
                new_inventory = resp.get_json()
                new_inventory["quantity"] = qty
                resp = self.app.put(
                    "/inventory/{}/condition/{}".format(new_inventory["product_id"], new_inventory["condition"]),
                    json=new_inventory,
                    content_type="application/json",
                )
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
                updated_inventory = resp.get_json()
                self.assertEqual(updated_inventory["quantity"], qty)
            else:
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_inventory_2(self):
        """Update an existing product in Inventory - 2"""
        global PERMS
        for p in PERMS:
            set_permissions(p)
            test_inventory = InventoryFactory()
            resp = self.app.post(
                "/inventory", json=test_inventory.serialize(), content_type="application/json"
            )
            if p:
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

                new_inventory = resp.get_json()
                new_inventory["quantity"] = 30
                resp = self.app.put(
                    "/inventory/{}/condition/{}".format(new_inventory["product_id"]+4, new_inventory["condition"]),
                    json=new_inventory,
                    content_type="application/json",
                )
                self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
            else:
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_inventory_activate(self):
        """Activate an existing Inventory"""
        global PERMS
        for p in PERMS:
            set_permissions(p)
            quantities = [0,1]
            for qty in quantities:
                test_inventory = InventoryFactory()
                test_inventory.quantity = qty
                resp = self.app.post(
                    "/inventory", json=test_inventory.serialize(), content_type="application/json"
                )
                if p:
                    new_inventory = resp.get_json()
                    self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
                    resp = self.app.put(
                        "/inventory/{}/condition/{}/activate".format(new_inventory["product_id"], new_inventory["condition"])
                    )
                    if test_inventory.quantity > 0:
                        self.assertEqual(resp.status_code, status.HTTP_200_OK)
                    else:
                        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
                else:
                    self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_inventory_deactivate(self):
        """Deactivate an existing Inventory"""
        global PERMS
        for p in PERMS:
            set_permissions(p)
            test_inventory = InventoryFactory()
            resp = self.app.post(
                "/inventory", json=test_inventory.serialize(), content_type="application/json"
            )
            if p:
                new_inventory = resp.get_json()
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
                resp = self.app.put(
                    "/inventory/{}/condition/{}/deactivate".format(new_inventory["product_id"], new_inventory["condition"])
                )
                self.assertEqual(resp.status_code, status.HTTP_200_OK)
            else:
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_inventory_restock(self):
        """Restock an inventory's Quantity"""
        global PERMS
        for p in PERMS:
            set_permissions(p)
            test_inventory = InventoryFactory()
            resp = self.app.post(
                "/inventory", json=test_inventory.serialize(), content_type="application/json"
            )
            if p:
                self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
                new_inventory = resp.get_json()
                body = {}
                amounts = [-1,0,1,2,3]
                for a in amounts:
                    key = 'amount'
                    if a >= 2:
                        key = 'amounty'
                    body[key] = a
                    resp = self.app.put(
                        "/inventory/{}/condition/{}/restock".format(new_inventory["product_id"], new_inventory["condition"]),
                        json=body,
                        content_type="application/json",
                    )
                    if key is not 'amount':
                        self.assertEqual(resp.status_code, status.HTTP_200_OK)
                    elif a > 0:
                        self.assertEqual(resp.status_code, status.HTTP_200_OK)
                    else:
                        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
            else:
                self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_updates_not_found(self):
        """Testing Updates NOT found"""
        set_permissions(BASE)
        pid = 9999
        cnd = "new"
        resp = self.app.put(
                "/inventory/{}/condition/{}".format(pid, cnd),
                json={},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp = self.app.put(
                "/inventory/{}/condition/{}/restock".format(pid, cnd),
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp = self.app.put(
                "/inventory/{}/condition/{}/activate".format(pid, cnd),
            )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        resp = self.app.put(
                "/inventory/{}/condition/{}/deactivate".format(pid, cnd),
            )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
