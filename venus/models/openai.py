"""
Basic Model API for OpenAI-like endpoints.
"""

import dotenv

from ..agent import Venus, VenusCode
from ..errors import InvalidParameter, InvalidProvider, ProviderConflict
from ..settings import Settings
from ..types import (GrokProvider, KnownModelName, ModelProfile, ModelSettings,
                     OpenAIModel, OpenAIProvider, Provider)

dotenv.load_dotenv()

settings = Settings()

Unset = type[None]


class OpenAI(VenusCode):
    """
    OpenAI is a subclass of Venus that provides an interface for interacting with OpenAI-compatible models.
    It allows you to set up the
    model, system prompt, and other configurations.
    """

    def __init__(
        self,
        model_name: str | KnownModelName,
        base_url: str | None = None,
        api_key: str | None = None,
        model_settings: ModelSettings | None = None,
        profile: ModelProfile | None = None,
        custom_provider: Provider | None = None,
        coding_agent: bool | Unset = Unset,
        init: bool = False,
        **options,  # options to pass to the Venus ctor if init set, otherwise to the OpenAIModel
    ):
        """
        Initialize the OpenAI model with the specified parameters.

        Args:
            model_name (str | KnownModelName): The name of the model to use.
            base_url (str): The base URL for the OpenAI API, defaults to settings.openai_base_url.
            api_key (str): The API key for authentication, defaults to settings.openai_api_key.
            system_prompt_role (str): The role for the system prompt, defaults to "system".
            model_settings (ModelSettings): Settings for the model, defaults to ModelSettings().
            profile (ModelProfile): Profile for the model, defaults to None.
            custom_provider (Provider): Custom provider for the model, defaults to None.
            coding_agent (bool): Whether to use coding agent capabilities, defaults to False.
            init (bool): Whether to initialize the model immediately, defaults to False.
            **options: Additional options for the provider.
        """
        if api_key is None:
            api_key = settings.openai_api_key

        if not isinstance(custom_provider, (Provider, type(None))):
            raise InvalidProvider(
                f"Provider got type {type(custom_provider).__name__!r}, "
                "expected subclass of Provider"
            )

        if (base_url or api_key) and custom_provider:
            raise ProviderConflict(
                "Cannot set base_url or api_key when using a custom provider."
            )

        self.provider = custom_provider or OpenAIProvider(
            base_url=base_url, api_key=api_key, **options if not init else {}
        )

        self.model = OpenAIModel(
            model_name=model_name,
            provider=self.provider,
            settings=model_settings,
            profile=profile,
        )

        if init:
            self.init(**options if init else {}, coding_agent=coding_agent)
        elif coding_agent is not Unset:
            raise InvalidParameter(
                "The 'coding_agent' parameter can only be set when 'init' is True."
            )

    def init(
        self,
        system_prompt: str | tuple = (),
        coding_agent: bool = False,
        **options,  # options to pass to the Venus ctor
    ) -> None:
        """
        Initialize the model with the specified system prompt and options.

        Args:
            system_prompt (str | tuple): The system prompt to use.
            coding_agent (bool): Whether to use coding agent capabilities.
            **options: Additional options for the model.
        """
        if not system_prompt:
            system_prompt = settings.system_prompt
        else:
            system_prompt = (
                system_prompt if isinstance(system_prompt, tuple) else (system_prompt,)
            )

        Base = Venus if not coding_agent else VenusCode
        if "coding_prompt" in options or "execution_allowed" in options:
            Base = VenusCode

        Base.__init__(self, model=self.model, system_prompt=system_prompt, **options)


class LMStudio(OpenAI):
    """
    LMStudio is a subclass of OpenAI that provides an interface for interacting with the LM Studio API.
    It allows you to set up the model, system prompt, and other configurations specific to LM Studio.
    """

    def __init__(
        self, model_name: str, base_url: str = "http://127.0.0.1:1234/v1", **kwargs
    ):
        """
        Initialize the LMStudio model with the specified parameters.

        Args:
            model_name (str): The name of the model to use.
            base_url (str): The base URL for the LM Studio API, defaults to "http://
            **kwargs: Additional options to pass venus.models.OpenAI constructor.
        """
        super().__init__(
            init=kwargs.pop("init", True),
            api_key="lm-studio",
            model_name=model_name,
            base_url=base_url or settings.lmstudio_base_url,
            **kwargs,
        )


class xAI(OpenAI):
    """
    xAI is a subclass of OpenAI that provides an interface for interacting with the Grok API.
    It allows you to set up the model, system prompt, and other configurations specific to Grok.
    """

    def __init__(
        self,
        model_name: str | None = None,
        grok_api_key: str | None = None,
        coding_agent: bool = False,
        **kwargs,
    ):
        """
        Initialize the Grok model with the specified parameters.

        Args:
            model_name (str): The name of the model to use, defaults to settings.model_name.
            base_url (str): The base URL for the Grok API, defaults to settings.grok_base_url.
            grok_api_key (str): The API key for authentication, defaults to settings.grok_api_key.
            **kwargs: Additional options to pass venus.models.OpenAI constructor.
        """

        super().__init__(
            init=True,
            coding_agent=coding_agent,
            custom_provider=GrokProvider(api_key=grok_api_key or settings.grok_api_key),
            model_name=model_name or settings.model_name,
            **kwargs,
        )


class Grok(xAI):
    """
    Grok is a subclass of xAI that provides an interface for interacting with the xAI API.
    It allows you to set up the model, system prompt, and other configurations specific to x
    """

    pass
