import json
import os
import re
import subprocess

from openai import OpenAI
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.layout.processors import Processor, Transformation
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea


def gradient_text(text, start_color=(30, 144, 255), end_color=(46, 204, 113)):
    text_obj = Text()
    visible_chars = [char for char in text if char != "\n"]
    visible_index = -1

    for char in text:
        if char == "\n":
            text_obj.append("\n")
            continue

        visible_index += 1
        if len(visible_chars) == 1:
            ratio = 0
        else:
            ratio = visible_index / (len(visible_chars) - 1)

        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        color = f"#{r:02x}{g:02x}{b:02x}"
        text_obj.append(char, style=f"bold {color}")

    return text_obj


def build_box_style(mode):
    color = "#1E90FF" if mode == "build" else "#FFA500"
    return Style.from_dict(
        {
            "frame.border": f"fg:{color}",
            "frame.label": f"fg:{color} bold",
            "text-area": "fg:#ffffff",
            "tag": "fg:#FFD700 bold",
        }
    )


class TagStripperProcessor(Processor):
    def apply_transformation(self, transformation_input):
        text = transformation_input.document.text
        fragments = []
        last = 0
        default_style = ""
        for match in re.finditer(r'/([A-Za-z_][A-Za-z0-9_]*)', text):
            if match.start() > last:
                fragments.append((default_style, text[last:match.start()]))
            fragments.append(("class:tag", match.group(1)))
            last = match.end()
        if last < len(text):
            fragments.append((default_style, text[last:]))
        return Transformation(fragments)


def format_prompt_tags(text):
    styled = Text()
    last = 0
    for match in re.finditer(r'/([A-Za-z_][A-Za-z0-9_]*)', text):
        if match.start() > last:
            styled.append(text[last:match.start()])
        styled.append(match.group(1), style="bold goldenrod1")
        last = match.end()
    styled.append(text[last:])
    return styled

SUPPORTED_FUNCTIONS = [
    {
        "name": "read",
        "description": "Read a file from the local repository.",
        "parameters": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string", "description": "Path of the file to read."}
            },
            "required": ["filePath"],
        },
    },
    {
        "name": "write",
        "description": "Write content to a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["filePath", "content"],
        },
    },
    {
        "name": "edit",
        "description": "Edit a file by replacing exact text.",
        "parameters": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string"},
                "find": {"type": "string"},
                "replace": {"type": "string"},
            },
            "required": ["filePath", "find", "replace"],
        },
    },
    {
        "name": "commands",
        "description": "Execute a shell command.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "listFiles",
        "description": "List files in a directory.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "recursive": {"type": "boolean"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "writeFile",
        "description": "Write a new file or replace an existing file.",
        "parameters": {
            "type": "object",
            "properties": {
                "filePath": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["filePath", "content"],
        },
    },
    {
        "name": "subagent",
        "description": "Run a subagent for specialized tasks.",
        "parameters": {
            "type": "object",
            "properties": {
                "agentType": {"type": "string"},
                "task": {"type": "string"},
                "context": {"type": "object"},
            },
            "required": ["agentType", "task"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web using Chromium and return a concise summary of results.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query to run in the browser."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "memory",
        "description": "Store valuable information in memory for future reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "memory": {"type": "string", "description": "Information to store in memory."},
            },
            "required": ["memory"],
        },

    }
]


def boxed_input(title=None):
    kb = KeyBindings()
    mode = "build"

    text_area = TextArea(
        multiline=False,
        wrap_lines=False,
        prompt="> ",
        style="class:text-area",
        input_processors=[TagStripperProcessor()],
    )

    def toggle_mode(event):
        nonlocal mode
        mode = "plan" if mode == "build" else "build"
        event.app.style = build_box_style(mode)
        event.app.invalidate()

    @kb.add("enter")
    def _submit(event):
        mode_tag = "/build-mode" if mode == "build" else "/plan-mode"
        event.app.exit(result=f"{mode_tag} {text_area.text}".strip())

    @kb.add("c-s")
    def _toggle_mode(event):
        toggle_mode(event)

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event):
        event.app.exit(result=None)

    frame = Frame(text_area, title=title)
    layout = Layout(HSplit([frame]))

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=build_box_style(mode),
        full_screen=False,
        mouse_support=False,
    )

    return app.run()


def parse_tool_calls(text):
    tool_pattern = r'(\w+)\s*\(\s*([^)]*)\s*\)'
    matches = re.finditer(tool_pattern, text)

    tools = []
    for match in matches:
        tool_name = match.group(1)
        if tool_name in ['read', 'write', 'edit', 'commands', 'listFiles', 'writeFile', 'subagent', 'web_search', 'memory']:
            tools.append(tool_name)

    return tools


def display_tool_progress(console, tool_name):
    messages = {
        'read': ('Reading file...', 'white'),
        'listFiles': ('Listing files...', 'white'),
        'write': ('Building...', 'white'),
        'writeFile': ('Building...', 'white'),
        'edit': ('Refactoring...', 'white'),
        'commands': ('Executing...', 'yellow'),
        'subagent': ('Delegating to specialist...', 'cyan'),
        'memory': ('Storing in memory...', 'white'),
    }

    if tool_name in messages:
        msg, color = messages[tool_name]
        console.print(f'[{color}]{msg}[/{color}]')


def load_system_prompt(filepath="Agents.md"):
    # Merge Agents.md (or provided filepath) with a local memories file when available.
    parts = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            parts.append(f.read())
    except FileNotFoundError:
        print(f"Warning: {filepath} not found.")

    # Prefer lowercase 'memories.md' but accept 'Memories.md' too.
    memories_candidates = ["memories.md", "Memories.md"]
    for mem in memories_candidates:
        try:
            if os.path.isfile(mem):
                with open(mem, "r", encoding="utf-8") as f:
                    parts.append("\n\n# Memories\n\n")
                    parts.append(f.read())
                break
        except Exception as e:
            print(f"Warning: failed to read {mem}: {e}")

    if parts:
        return "\n\n".join(parts)

    # Fallback default prompt
    print(f"Warning: neither {filepath} nor memories.md found. Using default system prompt.")
    return (
        "You are a helpful assistant for code development for First Tech "
        "Challenge (FTC) robotics teams. You are an expert in Java coding "
        "and provide optimal solutions to any and all problems"
    )


def extract_text_content(response_text):
    cleaned = re.sub(r'\w+\s*\(\s*[^)]*\s*\)', '', response_text)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def get_tool_calls_from_response(response):
    tool_calls = []
    for choice in getattr(response, "choices", []):
        msg = getattr(choice, "message", None)
        if not msg:
            continue
        function_call = getattr(msg, "function_call", None)
        if function_call:
            tool_calls.append({
                "name": function_call.name,
                "arguments": function_call.arguments,
            })
        tool_loop = getattr(msg, "tool_calls", None)
        if tool_loop:
            for call in tool_loop:
                tool_calls.append(call)
    return tool_calls


def execute_tool_call(tool_name, arguments):
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError as e:
            return f"Invalid tool arguments: {e}"

    if tool_name == "read":
        file_path = arguments.get("filePath")
        if not file_path:
            return "Missing filePath for read()"
        if not os.path.isfile(file_path):
            return f"File not found: {file_path}"
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
        
    if tool_name == "memory":
        memory = arguments.get("memory")
        if not memory:
            return "Missing memory for memory()"
        else:
        # Store the memory in Memories.md 
          with open("Memories.md", "a", encoding="utf-8") as f:
                f.write(f"{memory}\n")
        return f"Stored in memory: {memory}"

    if tool_name in ["write", "writeFile"]:
        file_path = arguments.get("filePath")
        content = arguments.get("content", "")
        if not file_path:
            return "Missing filePath for write()"
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote file: {file_path}"

    if tool_name == "edit":
        file_path = arguments.get("filePath")
        find = arguments.get("find", "")
        replace = arguments.get("replace", "")
        if not file_path:
            return "Missing filePath for edit()"
        if not os.path.isfile(file_path):
            return f"File not found: {file_path}"
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        if find not in text:
            return f"Pattern not found in {file_path}."
        new_text = text.replace(find, replace, 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_text)
        return f"Edited file: {file_path}"

    if tool_name == "commands":
        command = arguments.get("command", "")
        if not command:
            return "Missing command for commands()"
        result = subprocess.run(
            command,
            shell=True,
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
        )
        output = result.stdout.strip() or result.stderr.strip()
        if not output:
            output = f"Command completed with exit code {result.returncode}."
        return output

    if tool_name == "listFiles":
        path = arguments.get("path", ".")
        recursive = arguments.get("recursive", False)
        if not os.path.exists(path):
            return f"Path not found: {path}"
        if recursive:
            items = []
            for root, dirs, files in os.walk(path):
                for name in dirs + files:
                    items.append(os.path.relpath(os.path.join(root, name), path))
            return "\n".join(sorted(items))
        return "\n".join(sorted(os.listdir(path)))

    if tool_name == "web_search":
        query = arguments.get("query", "")
        if not query:
            return "Missing query for web_search()"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(f"https://www.google.com/search?q={query}", wait_until="domcontentloaded", timeout=120000)
                page.wait_for_timeout(3000)
                snippets = []
                for element in page.locator("div.g").all()[:4]:
                    try:
                        title = element.locator("h3").first.inner_text()
                    except Exception:
                        title = ""
                    try:
                        text = element.locator(".VwiC3b, .IsZvec").first.inner_text()
                    except Exception:
                        text = ""
                    if title or text:
                        snippets.append(f"{title}\n{text}".strip())
                browser.close()
                if snippets:
                    return "\n\n".join(snippets[:4])
                return page.locator("body").inner_text()[:4000]
        except Exception as e:
            return f"Web search failed: {e}"

    if tool_name == "subagent":
        return "Subagent execution is not supported in this CLI."

    return f"Unknown tool: {tool_name}"


def append_function_message(conversation_history, name, arguments):
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments)
    conversation_history.append(
        {
            "role": "assistant",
            "content": "",
            "function_call": {"name": name, "arguments": arguments},
        }
    )


def main():
    console = Console()
    console.clear()

    api_key = os.environ.get(
        "GROQ_API_KEY",
        "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",
    )

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
    )

    model_name = "openai/gpt-oss-120b"

    banner = (
        "███████╗████████╗ ██████╗      ██████╗ ██████╗ ██████╗ ███████╗\n"
        "██╔════╝╚══██╔══╝██╔════╝     ██╔════╝██╔═══██╗██╔══██╗██╔════╝\n"
        "█████╗     ██║   ██║          ██║     ██║   ██║██║  ██║█████╗  \n"
        "██╔══╝     ██║   ██║          ██║     ██║   ██║██║  ██║██╔══╝  \n"
        "██║        ██║   ╚██████╗     ╚██████╗╚██████╔╝██████╔╝███████╗\n"
        "╚═╝        ╚═╝    ╚═════╝      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝\n"
        "\n[ FTC Code CLI v1.0.0 ] FTC code is neither an official product nor affiliated with First and should not be treated as such"
    )
    console.print(gradient_text(banner))
    console.print(f"Model: [cyan]{model_name}[/cyan]")
    console.print("Type [bold yellow]'exit'[/bold yellow], [bold yellow]'quit'[/bold yellow], or press Esc/Ctrl+C to stop.\n")

    system_prompt = load_system_prompt()
    conversation_history = [{"role": "system", "content": system_prompt}]

    while True:
        try:
            user_input = boxed_input(title=None)

            if user_input is None:
                console.print("\n[bold blue]Goodbye![/bold blue]")
                break

            if user_input.strip().lower() in ["exit", "quit"]:
                console.print("\n[bold blue]Goodbye![/bold blue]")
                break

            if not user_input.strip():
                continue

            console.print("[bold cyan]You:[/bold cyan]", format_prompt_tags(user_input))
            conversation_history.append({"role": "user", "content": user_input})

            while True:
                with console.status(
                    "[white]Thinking...[/white]",
                    spinner="dots",
                    spinner_style="white",
                ):
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=conversation_history,
                        functions=SUPPORTED_FUNCTIONS,
                        function_call="auto",
                    )
                choice = response.choices[0]
                assistant_message = getattr(choice, "message", None)
                function_call = getattr(assistant_message, "function_call", None)
                assistant_reply = getattr(assistant_message, "content", None) or ""

                if not function_call:
                    narrative = extract_text_content(assistant_reply)
                    if narrative:
                        console.print("\n[bold magenta]AI >[/bold magenta]")
                        console.print(Markdown(narrative))
                    elif assistant_reply:
                        console.print("\n[bold magenta]AI >[/bold magenta]")
                        console.print(Markdown(assistant_reply))
                    conversation_history.append({"role": "assistant", "content": assistant_reply})
                    break

                tool_name = function_call.name
                tool_arguments = function_call.arguments
                display_tool_progress(console, tool_name)
                console.print(f"[dim]{tool_name} arguments: {tool_arguments}[/dim]\n")

                tool_result = execute_tool_call(tool_name, tool_arguments)
                console.print(f"[green]✓ {tool_result}[/green]\n")

                append_function_message(conversation_history, tool_name, tool_arguments)
                conversation_history.append(
                    {"role": "function", "name": tool_name, "content": tool_result}
                )

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold blue]Goodbye![/bold blue]")
            break
        except Exception as e:
            console.print(f"\n[bold red]API Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
