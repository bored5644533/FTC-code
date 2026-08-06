import sys
from openai import OpenAI
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text


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


def main():
    console = Console()

    # Hardcoded Groq API key (temporary usage)
    api_key = "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"

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key
    )

    model_name = "openai/gpt-oss-20b"

    banner = (
        "███████╗████████╗ ██████╗      ██████╗ ██████╗ ██████╗ ███████╗\n"
        "██╔════╝╚══██╔══╝██╔════╝     ██╔════╝██╔═══██╗██╔══██╗██╔════╝\n"
        "█████╗     ██║   ██║          ██║     ██║   ██║██║  ██║█████╗  \n"
        "██╔══╝     ██║   ██║          ██║     ██║   ██║██║  ██║██╔══╝  \n"
        "██║        ██║   ╚██████╗     ╚██████╗╚██████╔╝██████╔╝███████╗\n"
        "╚═╝        ╚═╝    ╚═════╝      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝\n"
        "\n[ FTC Code CLI v1.0.0 ] - Ready for development"
    )
    console.print(gradient_text(banner))
    console.print(f"Model: [cyan]{model_name}[/cyan]")
    console.print("Type [bold yellow]'exit'[/bold yellow], [bold yellow]'quit'[/bold yellow], or press Ctrl+C to stop.\n")

    # Maintain conversation history so the model remembers past messages
    conversation_history = [
        {"role": "system", "content": "You are a helpful assistant for code development for First Tech Challenge (FTC) robotics teams. You are an expert in Java coding and provide optimal solutions to any and all problems"}
    ]

    # Continuous Chat Loop (REPL)
    while True:
        try:
            # Get input directly inside the loop
            user_input = console.input("\n[bold cyan]You > [/bold cyan]")

            # Check for exit commands
            if user_input.strip().lower() in ["exit", "quit"]:
                console.print("[bold blue]Goodbye![/bold blue]")
                break

            # Skip empty inputs
            if not user_input.strip():
                continue

            # Append user message to history
            conversation_history.append({"role": "user", "content": user_input})

            # Call the Groq API with loading indicator
            with console.status(
                "[white]Thinking...[/white]",
                spinner="dots",
                spinner_style="white",
            ):
                response = client.chat.completions.create(
                    model=model_name,
                    messages=conversation_history
                )
                assistant_reply = response.choices[0].message.content

            # Append assistant response to history to maintain context
            conversation_history.append({"role": "assistant", "content": assistant_reply})

            # Print formatted response
            console.print("\n[bold magenta]AI >[/bold magenta]")
            console.print(Markdown(assistant_reply))

        except (KeyboardInterrupt, EOFError):
            # Gracefully handle Ctrl+C or Ctrl+D
            console.print("\n[bold blue]Goodbye![/bold blue]")
            break
        except Exception as e:
            console.print(f"\n[bold red]API Error:[/bold red] {e}")

if __name__ == "__main__":
    main()
