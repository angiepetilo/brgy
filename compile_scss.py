import sass
import os

scss_file = os.path.join('static', 'scss', 'main.scss')
css_file = os.path.join('static', 'css', 'main.css')

try:
    compiled_css = sass.compile(filename=scss_file, output_style='compressed')
    with open(css_file, 'w', encoding='utf-8') as f:
        f.write(compiled_css)
    print(f"Successfully compiled {scss_file} to {css_file} ({len(compiled_css)} bytes)")
except Exception as e:
    print(f"Error compiling SCSS: {e}")
