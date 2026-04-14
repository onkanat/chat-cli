"""
Example plugin for Ollama Chat CLI.

This plugin demonstrates how to create custom commands.
"""

from lib.plugins import PluginBase
from typing import Dict, List, Callable, Any
from rich.console import Console

console = Console()


class ExamplePlugin(PluginBase):
    """Example plugin with custom commands."""
    
    def __init__(self):
        super().__init__()
        self.name = "ExamplePlugin"
        self.version = "1.0.0"
        self.description = "Example plugin with custom commands"
        self.author = "Ollama Chat CLI"
    
    def get_commands(self) -> Dict[str, Callable]:
        return {
            "hello": self.hello_command,
            "calc": self.calc_command,
            "time": self.time_command
        }
    
    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "commands": list(self.get_commands().keys())
        }
    
    def hello_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Say hello to the user."""
        name = " ".join(args) if args else "World"
        console.print(f"[green]Hello, {name}! 👋[/green]")
    
    def calc_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Evaluates math expressions safely. Supports +, -, *, /, **, %, sqrt, sin, cos, tan, log, exp."""
        if not args:
            console.print("[yellow]Usage: /calc <expression>[/yellow]")
            console.print("[dim]Example: /calc (12 + 5) * 2[/dim]")
            return

        expression = " ".join(args)
        
        # Safe evaluation using AST
        import ast
        import math
        import operator

        # Supported operators
        operators = {
            ast.Add: operator.add, ast.Sub: operator.sub, 
            ast.Mult: operator.mul, ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
            ast.Pow: operator.pow, ast.USub: operator.neg, 
            ast.UAdd: operator.pos
        }

        # Supported functions
        functions = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, 
            "tan": math.tan, "log": math.log, "log10": math.log10,
            "exp": math.exp, "abs": abs, "ceil": math.ceil, "floor": math.floor
        }

        def eval_node(node):
            if isinstance(node, ast.Constant): # Python 3.8+ handles Num, Str, etc.
                if isinstance(node.value, (int, float)):
                    return node.value
                raise ValueError(f"Constant type {type(node.value)} not supported")
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](eval_node(node.left), eval_node(node.right))
            elif isinstance(node, ast.UnaryOp):
                return operators[type(node.op)](eval_node(node.operand))
            elif isinstance(node, ast.Call):
                func_name = node.func.id
                if func_name in functions:
                    args = [eval_node(arg) for arg in node.args]
                    return functions[func_name](*args)
                raise ValueError(f"Function {func_name} is not supported")
            elif isinstance(node, ast.Name):
                if node.id == "pi": return math.pi
                if node.id == "e": return math.e
                raise ValueError(f"Variable {node.id} is not supported")
            else:
                raise TypeError(f"Unsupported node type: {type(node).__name__}")

        try:
            tree = ast.parse(expression, mode='eval')
            result = eval_node(tree.body)
            console.print(f"[green]Result:[/green] [white]{expression} = {result}[/white]")
        except Exception as e:
            console.print(f"[red]Error parsing expression:[/red] {e}")
            console.print("[dim]Note: Variable assignment (set/get) and complex matrices are not supported.[/dim]")
    
    def time_command(self, args: List[str], context: Dict[str, Any]) -> None:
        """Show current time."""
        from datetime import datetime
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[blue]Current time: {current_time} 🕐[/blue]")
    
    def on_load(self) -> None:
        console.print("[green]✓ Example plugin loaded! 🚀[/green]")
    
    def on_unload(self) -> None:
        console.print("[yellow]📤 Example plugin unloaded[/yellow]")
