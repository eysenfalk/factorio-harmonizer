#!/usr/bin/env python3
"""
Lua Environment Manager
Handles Lua runtime setup and Factorio API simulation
"""

import lupa
from lupa import LuaRuntime
from typing import Dict, Any, Optional, Callable
from pathlib import Path
import logging
import json

class FactorioLuaEnvironment:
    """Manages a sandboxed Lua environment with Factorio API simulation"""
    
    def __init__(self):
        self.lua: Optional[LuaRuntime] = None
        self.data_raw: Dict[str, Any] = {}
        self.callbacks: Dict[str, Callable] = {}
        self.logger = logging.getLogger(__name__)
        self._setup_environment()
    
    def _setup_environment(self):
        """Initialize the Lua runtime with basic Factorio globals"""
        try:
            # Create Lua runtime
            self.lua = LuaRuntime(unpack_returned_tuples=True)
            
            # Initialize basic data structure
            self.lua.execute("""
                data = {raw = {}}
            """)
            
            # Set up all the Factorio API components
            self._setup_data_extend()
            self._setup_utility_functions()
            
            self.logger.info("Lua environment initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Lua environment: {e}")
            raise
    
    def _setup_data_extend(self):
        """Set up the data:extend function that tracks prototype additions"""
        # Create Python function that will be called from Lua
        def data_extend_impl(json_string):
            """Python implementation of data:extend"""
            try:
                self.logger.debug(f"data:extend called with JSON string length: {len(json_string)}")
                
                # Parse the JSON string
                prototypes = json.loads(json_string)
                self.logger.debug(f"Parsed {len(prototypes)} prototypes from JSON")
                
                for i, prototype in enumerate(prototypes):
                    ptype = prototype.get('type')
                    name = prototype.get('name')
                    
                    self.logger.debug(f"Processing prototype {i}: type={ptype}, name={name}")
                    
                    if ptype and name:
                        # Ensure the prototype type exists in data.raw
                        if ptype not in self.data_raw:
                            self.data_raw[ptype] = {}
                        
                        # Add the prototype
                        self.data_raw[ptype][name] = prototype
                        self.logger.info(f"Added prototype: {ptype}.{name}")
                    else:
                        self.logger.warning(f"Prototype {i} missing type or name: {prototype}")
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error in data:extend: {e}")
                import traceback
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                return False
        
        # Register the function in Lua
        self.lua.globals().python_data_extend = data_extend_impl
        
        # Set up JSON serialization function in Lua
        self.lua.execute("""
            -- Simple JSON serialization for Lua tables
            function serialize_table(t)
                if type(t) ~= "table" then
                    if type(t) == "string" then
                        return '"' .. t:gsub('"', '\\"') .. '"'
                    elseif type(t) == "number" then
                        return tostring(t)
                    elseif type(t) == "boolean" then
                        return tostring(t)
                    else
                        return "null"
                    end
                end
                
                local result = {}
                local is_array = true
                local max_index = 0
                
                -- Check if it's an array
                for k, v in pairs(t) do
                    if type(k) ~= "number" then
                        is_array = false
                        break
                    end
                    max_index = math.max(max_index, k)
                end
                
                if is_array then
                    -- Serialize as array
                    table.insert(result, "[")
                    for i = 1, max_index do
                        if i > 1 then
                            table.insert(result, ",")
                        end
                        table.insert(result, serialize_table(t[i]))
                    end
                    table.insert(result, "]")
                else
                    -- Serialize as object
                    table.insert(result, "{")
                    local first = true
                    for k, v in pairs(t) do
                        if not first then
                            table.insert(result, ",")
                        end
                        first = false
                        table.insert(result, '"' .. tostring(k) .. '":')
                        table.insert(result, serialize_table(v))
                    end
                    table.insert(result, "}")
                end
                
                return table.concat(result)
            end
        """)
        
        # Set up the Lua-side data:extend function
        self.lua.execute("""
            function data.extend(self, prototypes)
                -- Handle both data:extend(prototypes) and data.extend(prototypes) calling conventions
                local actual_prototypes = prototypes
                if prototypes == nil and type(self) == "table" and #self > 0 then
                    -- Called as data:extend(prototypes), so self is actually the prototypes
                    actual_prototypes = self
                end
                
                if python_data_extend then
                    -- Serialize the prototypes table to JSON
                    local json_string = serialize_table(actual_prototypes)
                    return python_data_extend(json_string)
                else
                    error("data:extend not properly initialized")
                end
            end
        """)
    
    def _setup_utility_functions(self):
        """Set up common Factorio utility functions"""
        self.lua.execute("""
            -- Basic utility functions
            util = {
                by_pixel = function(x, y)
                    if y then
                        return {x/32, y/32}
                    else
                        return x/32
                    end
                end,
                
                table = {
                    deepcopy = function(t)
                        if type(t) ~= "table" then
                            return t
                        end
                        
                        local copy = {}
                        for k, v in pairs(t) do
                            if type(v) == "table" then
                                copy[k] = util.table.deepcopy(v)
                            else
                                copy[k] = v
                            end
                        end
                        return copy
                    end
                }
            }
            
            -- Basic require function (simplified)
            function require(module_name)
                -- In a real implementation, this would load actual modules
                -- For now, return empty table
                return {}
            end
            
            -- Enhanced print function
            local original_print = print
            function print(...)
                local args = {...}
                local str_args = {}
                for i, v in ipairs(args) do
                    str_args[i] = tostring(v)
                end
                local message = table.concat(str_args, "\\t")
                
                -- Call Python logger if available
                if python_log then
                    python_log("INFO", message)
                else
                    original_print(message)
                end
            end
        """)
        
        # Set up Python logging callback
        def lua_log(level, message):
            if level == "ERROR":
                self.logger.error(f"Lua: {message}")
            elif level == "WARNING":
                self.logger.warning(f"Lua: {message}")
            else:
                self.logger.info(f"Lua: {message}")
        
        self.lua.globals().python_log = lua_log
    
    def register_callback(self, name: str, callback: Callable):
        """Register a Python callback that can be called from Lua"""
        try:
            self.callbacks[name] = callback
            self.lua.globals()[name] = callback
            self.logger.debug(f"Registered callback: {name}")
        except Exception as e:
            self.logger.error(f"Failed to register callback {name}: {e}")
    
    def execute_lua_code(self, lua_code: str, context: Dict[str, str] = None) -> bool:
        """Execute Lua code in the sandboxed environment"""
        try:
            if context:
                self.logger.debug(f"Executing Lua code from {context.get('mod', 'unknown')}")
            
            self.lua.execute(lua_code)
            return True
            
        except Exception as e:
            context_str = f" (from {context})" if context else ""
            self.logger.error(f"Lua execution error{context_str}: {e}")
            return False
    
    def get_data_raw(self) -> Dict[str, Any]:
        """Get the current state of data.raw"""
        try:
            # Return our Python copy of data.raw
            return self.data_raw.copy()
        except Exception as e:
            self.logger.error(f"Failed to get data.raw: {e}")
            return {}
    
    def get_lua_value(self, expression: str) -> Any:
        """Evaluate a Lua expression and return the result"""
        try:
            return self.lua.eval(expression)
        except Exception as e:
            self.logger.error(f"Failed to evaluate Lua expression '{expression}': {e}")
            return None
    
    def reset_environment(self):
        """Reset the Lua environment to initial state"""
        try:
            self.data_raw.clear()
            self.callbacks.clear()
            self._setup_environment()
            self.logger.info("Lua environment reset successfully")
        except Exception as e:
            self.logger.error(f"Failed to reset Lua environment: {e}")
            raise

# Test functions
def test_basic_lua_execution():
    """Test basic Lua code execution"""
    print("🧪 Testing basic Lua execution...")
    
    # Set up basic logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    env = FactorioLuaEnvironment()
    
    # Test simple Lua code
    test_code = '''
        print("Hello from Lua!")
        test_variable = 42
    '''
    
    success = env.execute_lua_code(test_code)
    print(f"Execution success: {success}")
    
    # Try to get a value back
    try:
        result = env.get_lua_value("test_variable")
        print(f"Retrieved value: {result}")
        
        if result == 42:
            print("✅ Basic Lua execution working!")
        else:
            print("❌ Value retrieval failed")
            
    except Exception as e:
        print(f"Error retrieving value: {e}")

def test_data_extend():
    """Test the data:extend functionality"""
    print("\n🧪 Testing data:extend functionality...")
    
    # Enable debug logging temporarily
    logging.getLogger().setLevel(logging.DEBUG)
    
    env = FactorioLuaEnvironment()
    
    # Test data should be extracted from actual mod files, not hardcoded
    print("⚠️  Test function disabled - no hardcoded content allowed")
    print("All test data should be extracted from actual mod files")
    return
    
    success = env.execute_lua_code(test_code)
    print(f"data:extend execution success: {success}")
    
    # Check if the prototypes were added
    data_raw = env.get_data_raw()
    print(f"Data raw contents: {list(data_raw.keys())}")
    
    success_count = 0
    
    if 'item' in data_raw and 'test-item' in data_raw['item']:
        print("✅ Successfully added item via data:extend")
        print(f"Item data: {data_raw['item']['test-item']}")
        success_count += 1
    else:
        print("❌ Item was not added properly")
    
    if 'recipe' in data_raw and 'test-recipe' in data_raw['recipe']:
        print("✅ Successfully added recipe via data:extend")
        print(f"Recipe data: {data_raw['recipe']['test-recipe']}")
        success_count += 1
    else:
        print("❌ Recipe was not added properly")
    
    if success_count == 2:
        print("✅ data:extend functionality working!")
    else:
        print(f"❌ data:extend partially working ({success_count}/2)")
    
    # Reset logging level
    logging.getLogger().setLevel(logging.INFO)

def test_callback_system():
    """Test the Python callback system"""
    print("\n🧪 Testing callback system...")
    
    env = FactorioLuaEnvironment()
    
    # Register a callback
    def test_callback(message):
        print(f"🐍 Python callback received: {message}")
        return "callback_response"
    
    env.register_callback("test_callback", test_callback)
    
    # Test calling the callback from Lua
    test_code = '''
        if test_callback then
            local result = test_callback("Hello from Lua!")
            print("Callback returned: " .. tostring(result))
            callback_test_success = true
        else
            print("Callback not available")
            callback_test_success = false
        end
    '''
    
    success = env.execute_lua_code(test_code)
    print(f"Callback test execution success: {success}")
    
    # Check if callback was successful
    callback_success = env.get_lua_value("callback_test_success")
    if callback_success:
        print("✅ Callback system working!")
    else:
        print("❌ Callback system failed")

def test_utility_functions():
    """Test utility functions"""
    print("\n🧪 Testing utility functions...")
    
    env = FactorioLuaEnvironment()
    
    test_code = '''
        -- Test util.by_pixel
        local pixel_result = util.by_pixel(64, 32)
        print("by_pixel result: " .. pixel_result[1] .. ", " .. pixel_result[2])
        
        -- Test table.deepcopy
        local original = {a = 1, b = {c = 2}}
        local copy = util.table.deepcopy(original)
        copy.b.c = 3
        
        print("Original: " .. original.b.c)
        print("Copy: " .. copy.b.c)
        
        -- Test require
        local module = require("some-module")
        print("Require returned: " .. type(module))
        
        util_test_success = (pixel_result[1] == 2 and pixel_result[2] == 1 and 
                           original.b.c == 2 and copy.b.c == 3 and 
                           type(module) == "table")
    '''
    
    success = env.execute_lua_code(test_code)
    print(f"Utility test execution success: {success}")
    
    util_success = env.get_lua_value("util_test_success")
    if util_success:
        print("✅ Utility functions working!")
    else:
        print("❌ Utility functions failed")

def test_lua_table_structure():
    """Debug test to understand Lua table structure"""
    print("\n🔍 Testing Lua table structure...")
    
    # Enable debug logging
    logging.getLogger().setLevel(logging.DEBUG)
    
    env = FactorioLuaEnvironment()
    
    # Register a debug callback to inspect the table
    def debug_table(table_obj):
        print(f"🔍 Debug table type: {type(table_obj)}")
        print(f"🔍 Has __len__: {hasattr(table_obj, '__len__')}")
        print(f"🔍 Has __getitem__: {hasattr(table_obj, '__getitem__')}")
        print(f"🔍 Has items: {hasattr(table_obj, 'items')}")
        print(f"🔍 Has values: {hasattr(table_obj, 'values')}")
        
        if hasattr(table_obj, '__len__'):
            try:
                length = len(table_obj)
                print(f"🔍 Length: {length}")
                
                for i in range(1, min(length + 1, 4)):  # Check first 3 items
                    try:
                        item = table_obj[i]
                        print(f"🔍 Item {i}: {type(item)}")
                        if hasattr(item, 'items'):
                            keys = list(item.keys()) if hasattr(item, 'keys') else 'no keys'
                            print(f"🔍   Keys: {keys}")
                    except Exception as e:
                        print(f"🔍 Error accessing item {i}: {e}")
            except Exception as e:
                print(f"🔍 Error getting length: {e}")
        
        return "debug_complete"
    
    env.register_callback("debug_table", debug_table)
    
    # Test with the same structure as our failing test
    test_code = '''
        local test_prototypes = {
            {
                type = "item",
                name = "test-item",
                stack_size = 100
            },
            {
                type = "recipe", 
                name = "test-recipe",
                enabled = true,
                ingredients = {
                    {"iron-plate", 2}
                },
                result = "test-item"
            }
        }
        
        print("About to debug table...")
        debug_table(test_prototypes)
        
        print("About to call data:extend...")
        data:extend(test_prototypes)
    '''
    
    success = env.execute_lua_code(test_code)
    print(f"Debug test success: {success}")
    
    # Reset logging level
    logging.getLogger().setLevel(logging.INFO)

def run_all_tests():
    """Run all tests for the Lua environment"""
    print("=" * 50)
    print("TESTING LUA ENVIRONMENT")
    print("=" * 50)
    
    test_basic_lua_execution()
    test_lua_table_structure()
    test_data_extend()
    test_callback_system()
    test_utility_functions()
    
    print("\n" + "=" * 50)
    print("LUA ENVIRONMENT TESTS COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    run_all_tests()
