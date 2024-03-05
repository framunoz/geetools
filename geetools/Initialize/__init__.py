"""Tools for the ``ee.Initialize`` function."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Optional

import ee
from google.oauth2.credentials import Credentials

from geetools.accessors import register_function_accessor

_project_id: Optional[str] = None
"The project Id used by the current user."


@register_function_accessor(ee.Initialize, "geetools")
class InitializeAccessor:
    """Toolbox for the ``ee.Initialize`` function."""

    def __init__(self, obj: Callable):
        """Initialize the class."""
        self._obj = obj

    @staticmethod
    def from_user(name: str = "", credential_pathname: str = "", project: str = "") -> None:
        """Initialize Earthengine API using a specific user.

        Equivalent to the ``ee.initialize`` function but with a specific credential file stored in the machine by the ``ee.Authenticate.to_user`` function.

        Args:
            name: The name of the user as saved when created. use default if not set
            credential_pathname: The path to the folder where the credentials are stored. If not set, it uses the default path
            project: The project_id to use. If not set, it uses the default project_id of the saved credentials.

        Example:
            .. code-block:: python

                import ee
                import geetools

                ee.Initialize.from_user("test")

                # check that GEE is connected
                ee.Number(1).getInfo()
        """
        # gather global variable to be modified
        global _project_id

        # set the user profile information
        name = f"credentials{name}"
        credential_pathname = credential_pathname or ee.oauth.get_credentials_path()
        credential_folder = Path(credential_pathname).parent
        credential_path = credential_folder / name

        # check if the user exists
        if not credential_path.exists():
            msg = "Please register this user first by using geetools.User.create first"
            raise ee.EEException(msg)

        # Set the credential object and Init GEE API
        tokens = json.loads((credential_path / name).read_text())
        credentials = Credentials(
            None,
            refresh_token=tokens["refresh_token"],
            token_uri=ee.oauth.TOKEN_URI,
            client_id=tokens["client_id"],
            client_secret=tokens["client_secret"],
            scopes=ee.oauth.SCOPES,
        )
        ee.Initialize(credentials)

        # save the project_id in a dedicated global variable as it's not saved
        # from GEE side
        _project_id = project or tokens["project_id"]


@register_function_accessor(ee.Initialize, "geetools")
def project_id() -> str:
    """Get the project_id of the current account.

    Returns:
        The project_id of the connected profile

    Raises:
        RuntimeError: If the account is not initialized.

    Examples:
        .. code-block::

            import ee, geetools

            ee.Initialize.geetools.project_id()
    """
    if _project_id is None:
        raise RuntimeError("The GEE account is not initialized")
    return _project_id
