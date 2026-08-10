#Handle LLM usage, whether it's Groq, OpenCode, or Llama.cpp
provider = input{"Provider:?"}
 banner = (
        "███████╗████████╗ ██████╗      ██████╗ ██████╗ ██████╗ ███████╗\n"
        "██╔════╝╚══██╔══╝██╔════╝     ██╔════╝██╔═══██╗██╔══██╗██╔════╝\n"
        "█████╗     ██║   ██║          ██║     ██║   ██║██║  ██║█████╗  \n"
        "██╔══╝     ██║   ██║          ██║     ██║   ██║██║  ██║██╔══╝  \n"
        "██║        ██║   ╚██████╗     ╚██████╗╚██████╔╝██████╔╝███████╗\n"
        "╚═╝        ╚═╝    ╚═════╝      ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝\n"
        "\n[ FTC Code CLI v1.0.0 ] FTC code is neither an official product nor affiliated with First and should not be treated as such"
    )
def main():
   print ("Welcome to")
   print (banner)
   provider = input (" Please choose your provider \n 1. Groq \n 2. Llama.cpp \n Number 1-2: ")
   if provider = 1
      provider = "groq"
   elif provider = 2
         provider = "Llama.cpp"
   temperature = input("Please choose a temperature (creativity) 0.0-1.0:")

   api_key = input("what is your api key?:")
   with open("providerinfo.txt", "a", encoding="utf-8") as f:
                   f.write(f"{provider}\n")
   with open("providerinfo.txt", "a", encoding="utf-8") as f:
                  f.write(f"{temperature}\n")
   with open("providerinfo.txt", "a", encoding="utf-8") as f:
                  f.write(f"{api_key}\n")
   return provider, temperature, api_key
main():

