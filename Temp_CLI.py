import os
import re

from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from prompt_toolkit import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout
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


BOX_STYLE = Style.from_dict(
    {
        "frame.border": "fg:#1E90FF",
        "frame.label": "fg:#1E90FF bold",
        "text-area": "fg:#ffffff",
    }
)


def boxed_input(title=None):
    
    kb = KeyBindings()

    text_area = TextArea(
        multiline=False,
        wrap_lines=False,
        prompt="> ",
        style="class:text-area",
    )

    @kb.add("enter")
    def _submit(event):
        event.app.exit(result=text_area.text)

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event):
        event.app.exit(result=None)

    frame = Frame(text_area, title=title)
    layout = Layout(HSplit([frame]))

    app = Application(
        layout=layout,
        key_bindings=kb,
        style=BOX_STYLE,
        full_screen=False,
        mouse_support=False,
    )

    return app.run()


def parse_tool_calls(text):
    """Extract and parse tool calls from agent response."""
    tool_pattern = r'(\w+)\s*\(\s*([^)]*)\s*\)'
    matches = re.finditer(tool_pattern, text)
    
    tools = []
    for match in matches:
        tool_name = match.group(1)
        if tool_name in ['read', 'write', 'edit', 'commands', 'listFiles', 'writeFile', 'subagent']:
            tools.append(tool_name)
    
    return tools


def display_tool_progress(console, tool_name):
    """Display contextual progress message for tool execution."""
    messages = {
        'read': ('📖 Reading file...', 'cyan'),
        'listFiles': ('📂 Listing files...', 'cyan'),
        'write': ('🔨 Building...', 'yellow'),
        'writeFile': ('🔨 Building...', 'yellow'),
        'edit': ('✏️  Refactoring...', 'yellow'),
        'commands': ('⚙️  Executing...', 'magenta'),
        'subagent': ('🤖 Delegating to specialist...', 'cyan'),
    }
    
    if tool_name in messages:
        msg, color = messages[tool_name]
        console.print(f'[{color}]{msg}[/{color}]')


def load_system_prompt(filepath="Agents.md"):
    """Load system prompt from Agents.md file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Warning: {filepath} not found. Using default system prompt.")
        return (
            "You are a helpful assistant for code development for First Tech "
            "Challenge (FTC) robotics teams. You are an expert in Java coding "
            "and provide optimal solutions to any and all problems"
        )


def extract_text_content(response_text):
    """Extract only the text content, filtering out tool call syntax."""
    # Remove tool call patterns to show only narrative text
    cleaned = re.sub(r'\w+\s*\(\s*[^)]*\s*\)', '', response_text)
    cleaned = cleaned.strip()
    return cleaned if cleaned else None


def main():
    console = Console()
    console.clear()  # clear the terminal once on launch

    # Hardcoded Groq API key (free tier). Override with GROQ_API_KEY if set.
    api_key = os.environ.get(
        "GROQ_API_KEY",
        "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",
    )

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
    )

    model_name = "openai/gpt-oss-20b"

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
    conversation_history = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]
    
    executing_tools = False
    
    while True:
        try:
            user_input = boxed_input(title=None)

            if user_input is None:  # Esc / Ctrl+C inside the box
                console.print("\n[bold blue]Goodbye![/bold blue]")
                break

            if user_input.strip().lower() in ["exit", "quit"]:
                console.print("[bold blue]Goodbye![/bold blue]")
                break

            if not user_input.strip():
                continue

            console.print(f"[bold cyan]You:[/bold cyan] {user_input}")
            conversation_history.append({"role": "user", "content": user_input})

            with console.status(
                "[white]Thinking...[/white]",
                spinner="dots",
                spinner_style="white",
            ):
                response = client.chat.completions.create(
                    model=model_name,
                    messages=conversation_history,
                )
                assistant_reply = response.choices[0].message.content

            # Detect if agent is using tools
            detected_tools = parse_tool_calls(assistant_reply)
            
            if detected_tools:
                executing_tools = True
                console.print("\n[bold cyan]Agent executing:[/bold cyan]")
                for tool in detected_tools:
                    display_tool_progress(console, tool)
                
                console.print()  # spacing
            
            # Extract and display narrative response (non-tool content)
            narrative = extract_text_content(assistant_reply)
            if narrative:
                console.print("\n[bold magenta]AI >[/bold magenta]")
                console.print(Markdown(narrative))
            elif detected_tools:
                # If only tools were called, acknowledge completion
                console.print("[bold green]✓ Operations completed successfully[/bold green]\n")
            
            executing_tools = False
            conversation_history.append({"role": "assistant", "content": assistant_reply})

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold blue]Goodbye![/bold blue]")
            break
        except Exception as e:
            console.print(f"\n[bold red]API Error:[/bold red] {e}")


if __name__ == "__main__":
    main()
