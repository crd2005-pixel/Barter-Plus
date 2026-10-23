import re

with open('unificador_listas/app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Make sure we don't duplicate the functions if they're already there from my previous append.
# They are at the very end of the file right now.
# We'll just move them up right before App class.

# First, read the appended functions out of the end of the file.
func1_def = "def limpiar_importe_ar("
func2_def = "def extraer_productos_de_pdf("

func1_pos = content.rfind(func1_def)

if func1_pos != -1:
    extracted_funcs = content[func1_pos:]
    content_without_funcs = content[:func1_pos]

    # Find the position of class App(ctk.CTk):
    app_class_pos = content_without_funcs.find("class App(ctk.CTk):")

    if app_class_pos != -1:
        new_content = content_without_funcs[:app_class_pos] + extracted_funcs + "\n\n" + content_without_funcs[app_class_pos:]
        with open('unificador_listas/app.py', 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Successfully moved functions above the App class.")
    else:
        print("App class not found")
else:
    print("Functions not found at the end of the file.")
