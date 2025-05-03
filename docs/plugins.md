# Plugin Architecture – Nagatha Assistant

Nagatha can be extended at runtime via *plugins*.  A plugin is a Python module
living in `src/nagatha_assistant/plugins/` that subclasses
`nagatha_assistant.core.plugin.Plugin`.

Why plugins?
• Cleanly isolate feature code from the chat core.
• Let the LLM call functions (OpenAI *tools* API) without shipping every tool
  to every user.
• Easy to develop: drop a file, restart Nagatha, done.

Lifecycle
---------
1. **Discovery** – `PluginManager` imports every module in the package and
   instantiates each `Plugin` subclass it finds.
2. **Setup** – `await plugin.setup(config)` is invoked (empty `config` for now).
3. **Runtime** – The JSON-schema returned by `plugin.function_specs()` is
   forwarded to OpenAI ChatCompletion.  When the model requests a
   `function_call`, `PluginManager.call_function()` routes to the right
   plugin’s `call()` coroutine and returns its string result to the chat loop.
4. **Teardown** – on application exit `await plugin.teardown()` is called.

Minimal template
----------------
```python
from nagatha_assistant.core.plugin import Plugin


class EchoPlugin(Plugin):
    name = "echo"
    version = "0.1"

    async def setup(self, config):
        pass

    async def teardown(self):
        pass

    def function_specs(self):
        return [
            {
                "name": "echo",
                "description": "Return the provided text",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            }
        ]

    async def call(self, name, arguments):
        if name == "echo":
            return arguments.get("text", "")
        raise ValueError("Unknown function")
```

Logging
-------
Each plugin can use the standard `logging` module.  With `LOG_LEVEL=DEBUG`
you will see lines like:

```
INFO  nagatha_assistant.core.plugin  Discovered plugin 'echo' v0.1
DEBUG nagatha_assistant.plugins.echo EchoPlugin returning 'hello'
INFO  nagatha_assistant.core.plugin  Plugin 'echo' executed function 'echo'
```

Testing
-------
See `tests/test_chat_plugins.py` for an example that patches the OpenAI client
and verifies that the chat pipeline executes the plugin.
