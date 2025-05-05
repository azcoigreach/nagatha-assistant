 # How to Create a Nagatha Plugin
 
 Nagatha can be extended at runtime through plugins. A plugin is a Python module that lives in the `src/nagatha_assistant/plugins/` directory and subclasses the base `Plugin` class found in `nagatha_assistant/core/plugin.py`.
 
 ## Overview
 
 A plugin allows you to add custom functionality to Nagatha, enabling the chat agent to discover and execute plugin functions via OpenAI function calling. Out of the box, Nagatha provides several plugins (e.g. the `echo` plugin) as examples.
 
 ## Plugin Structure
 
 Each plugin must:
 
 - Reside in the `src/nagatha_assistant/plugins/` directory.
 - Subclass the `Plugin` base class (`from nagatha_assistant.core.plugin import Plugin`).
 - Define two essential class attributes:
   - `name`: A unique identifier for the plugin.
   - `version`: The plugin's version (e.g. "0.1.0").
 
 ## Required Methods
 
 Implement the following methods in your plugin:
 
 1. **setup(self, config: Dict[str, Any]) -> None**  
    Perform initialization and configuration. For simple plugins, this may simply pass.
 
 2. **teardown(self) -> None**  
    Clean up any resources on shutdown.
 
 3. **function_specs(self) -> List[Dict[str, Any]]**  
    Return a list of function specifications used to expose plugin functionality.
    Each function spec should include:
    - `name`: The function name.
    - `description`: A brief description.
    - `parameters`: A JSON Schema describing expected input parameters.
 
 4. **call(self, name: str, arguments: Dict[str, Any]) -> str**  
    Execute the function matching the specified `name` with the given `arguments`. Validate and handle errors appropriately.
 
 ## Example Plugin
 
 Below is an example based on the `echo` plugin:
 
 ```python
 from nagatha_assistant.core.plugin import Plugin
 
 
 class EchoPlugin(Plugin):
     """A trivial plugin that returns the text provided to it."""
 
     name = "echo"
     version = "0.1.0"
 
     async def setup(self, config: dict) -> None:
         # No setup required.
         return None
 
     async def teardown(self) -> None:
         # No teardown required.
         return None
 
     def function_specs(self) -> list:
         return [{
             "name": "echo",
             "description": "Return exactly the text that was passed in.",
             "parameters": {
                 "type": "object",
                 "properties": {
                     "text": {
                         "type": "string",
                         "description": "The text to echo back."
                     }
                 },
                 "required": ["text"]
             }
         }]
 
     async def call(self, name: str, arguments: dict) -> str:
         if name != "echo":
             raise ValueError(f"EchoPlugin can only handle 'echo', not {name}")
         return str(arguments.get("text", ""))
 ```
 
 ## Best Practices
 
 - **Unique Naming:** Ensure each plugin has a unique `name` attribute to avoid conflicts.
 - **Clear Error Handling:** Validate the function calls and provide meaningful error messages.
 - **JSON Schema:** Adhere to JSON Schema standards in `function_specs` for reliable integration.
 - **Testing:** Thoroughly test your plugin. Review existing tests in `tests/` for examples.
 
 ## Final Notes
 
 Once your plugin is created, Nagatha will automatically discover it during startup. For more details on the plugin system, see the main plugins documentation in `docs/plugins.md`.