import requests
import json
import os
import logging
import re
from typing import Literal, Optional, Union, Dict, Any, TypedDict

client_version = "python-0.0.2-dev"  # Version of the HackDB client

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

WHERE_OPERATORS = [
    "equals",
    "gt",
    "lt",
    "gte",
    "lte",
    "contains",
    "in"
]

class OperatorDict(TypedDict, total=False):
    equals: Any
    gt: Any
    lt: Any
    gte: Any
    lte: Any
    contains: Any
    in_: list

class ModelProxy:
    def __init__(self, model_name, db_connection):
        self._model_name = model_name
        self._db_connection = db_connection
        if db_connection.debug:
            print(f"Accessed model: {self._model_name}")

    def find_many(self, where: dict[str, OperatorDict] = None, order=None, include=None, limit=50):
        """
        Find multiple records in the database.

        Parameters:
        where (dict): A dictionary specifying the conditions for filtering records.
            Example:
                {
                    "id": {"equals": 5},
                    "name": {"contains": "bob"},
                    "age": {"gt": 18, "lt": 65}
                }
            Supported operators: "equals", "gt", "lt", "gte", "lte", "contains", "in"
            For IntelliSense, use: WHERE_OPERATORS

        order (str): Optional. The field by which to order the results. WIP
        include (list): Optional. A list of related models to include in the results. WIP
        Returns:
        list: A list of records matching the specified conditions.
        """
        query_dict = {}
        if where is not None:
            query_dict["lookup_string"] = json.dumps(where)
        query_dict["limit"] = limit
        # Remove None values from the dictionary
        query_dict = {k: v for k, v in query_dict.items() if v is not None}

        if not self._db_connection.connected:
            raise ValueError("Database connection is not established.")

        response = requests.get(
            f"{self._db_connection.base_url}/tables/{self._model_name}/findmany",
            headers={"Authorization": f"Bearer {self._db_connection.token}"},
            params=query_dict
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to retrieve data: {response.status_code} - {response.text}")
            return []

    def delete(self, where=None):
        """
        Delete records from the database.

        Parameters:
        where (dict): A dictionary specifying the conditions for deleting records.
            Example:
                {
                    "id": {"equals": 5},
                    "name": {"contains": "bob"}
                }
            Supported operators: "equals", "gt", "lt", "gte", "lte", "contains", "in"
            For IntelliSense, use: WHERE_OPERATORS

        Returns:
        bool: True if deletion was successful, False otherwise.
        """
        query_dict = {}
        if where is not None:
            query_dict["lookup_string"] = json.dumps(where)
        # Remove None values from the dictionary
        query_dict = {k: v for k, v in query_dict.items() if v is not None}

        if not self._db_connection.connected:
            raise ValueError("Database connection is not established.")

        response = requests.delete(
            f"{self._db_connection.base_url}/tables/{self._model_name}/delete",
            headers={"Authorization": f"Bearer {self._db_connection.token}"},
            params=query_dict
        )

        if response.status_code == 200:
            return True
        else:
            logger.error(f"Failed to delete data: {response.status_code} - {response.text}")
            return False

    def create(self, data: dict):
        """
        Create a new record in the database.

        Parameters:
        data (dict): A dictionary containing structured (matching the table you are inserting to) data for the new record.
            Example:
                {
                    "name": "Alice",
                    "age": 30,
                    "email": "alice@example.com"
                }
        Returns:
        bool: True if creation was successful, False otherwise.
        """
        query_dict = {"data": json.dumps(data)}
        if not self._db_connection.connected:
            raise ValueError("Database connection is not established.")

        response = requests.post(
            f"{self._db_connection.base_url}/tables/{self._model_name}/create",
            headers={"Authorization": f"Bearer {self._db_connection.token}"},
            json=query_dict
        )

        if response.status_code == 201:
            return True
        else:
            logger.error(f"Failed to create record: {response.status_code} - {response.text}")
            return False

    def count(self, where: dict[str, OperatorDict] = None):
        """
        Count the number of records in the database.

        Parameters:
        where (dict): A dictionary specifying the conditions for counting records.
            Example:
                {
                    "id": {"equals": 5},
                    "name": {"contains": "bob"}
                }
            Supported operators: "equals", "gt", "lt", "gte", "lte", "contains", "in"
            For IntelliSense, use: WHERE_OPERATORS

        Returns:
        int: The count of records matching the specified conditions.
        """
        query_dict = {}
        if where is not None:
            query_dict["lookup_string"] = json.dumps(where)
        # Remove None values from the dictionary
        query_dict = {k: v for k, v in query_dict.items() if v is not None}

        if not self._db_connection.connected:
            raise ValueError("Database connection is not established.")

        response = requests.get(
            f"{self._db_connection.base_url}/tables/{self._model_name}/count",
            headers={"Authorization": f"Bearer {self._db_connection.token}"},
            params=query_dict
        )

        if response.status_code == 200:
            return response.json().get("count", 0)
        else:
            logger.error(f"Failed to count records: {response.status_code} - {response.text}")
            return 0

# --- HackDB Class ---

class HackDB:
    def __init__(self, token:str=None, base_url:str=None):
        self.token = token or os.getenv("HACKDB_TOKEN")
        self.base_url = base_url or "https://hackdb.hexagonical.ch/api/sdk/v1"
        self.debug = False  # Default to not in debug mode
        self.connected = False  # Initialize connected status
        if not self.token:
            raise ValueError("HACKDB_TOKEN must be set either as an argument or as an environment variable.")
        else:
            # Validate the token format
            if not re.match(r"^hkdb_tkn_[a-f0-9\-]{36}$", self.token):
                raise ValueError("Invalid token format.")

            response = requests.get(f"{self.base_url}/validatetoken", headers={"Authorization": f"Bearer {self.token}"})

            if response.status_code == 200:
                self.connected = True
                data = response.json()
                if data.get("valid"):
                    self.connected = True
                    print("Successfully connected to HackDB. (Backend version: {}, Client version: {})".format(data.get("backendversion", "unknown"), client_version))
                else:
                    raise ValueError("Invalid token. Please check your token.")

        self._db_connection = self # Initialize _db_connection

    def __getattr__(self, name):
        if not self.connected:
            raise AttributeError(f"HackDB instance is not connected. Cannot access attribute '{name}'.")

        if self.debug:
            print(f"Attempting to access attribute: {name}")

        return ModelProxy(name, self._db_connection)

    def __repr__(self):
        if self.connected:
            return f"<HackDB Instance(token={self.token[:16] + '*' * 16}, base_url={self.base_url})>"
        else:
            return "<HackDB Instance (not connected)>"

    def get_tables(self):
        """
        Retrieve a list of all tables in the database.
        
        Returns:
        list: A list of table names. eg. ["users", "orders", "products"]
        """
        if not self.connected:
            raise ValueError("HackDB instance is not connected. Cannot retrieve tables.")
        response = requests.get(f"{self.base_url}/tables", headers={"Authorization": f"Bearer {self.token}"})
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to retrieve tables: {response.status_code} - {response.text}")
            return []

    def get_credits(self):
        """
        Retrieve the current credits for the HackDB instance.
        
        Returns:
        int: The number of credits available.
        """
        if not self.connected:
            raise ValueError("HackDB instance is not connected. Cannot retrieve credits.")
        response = requests.get(f"{self.base_url}/credits", headers={"Authorization": f"Bearer {self.token}"})
        if response.status_code == 200:
            return response.json().get("credits", 0)
        else:
            logger.error(f"Failed to retrieve credits: {response.status_code} - {response.text}")
            return 0