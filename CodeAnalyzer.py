import os
import sys
import json
import pyfiglet
from termcolor import colored
from pathlib import Path

# Fayil qisqartmalari
response_files = {
    # Web dasturlash
   'html': 'respons_html.html',
   'css': 'respons_css.css',
   'js': 'respons_js.js',
   'ts': 'respons_ts.ts',
   'php': 'respons_php.php',
   'asp': 'respons_asp.asp',
   'aspx': 'respons_aspx.aspx',
   'vue': 'respons_vue.vue', 
   'jsx': 'respons_jsx.jsx',
   'tsx': 'respons_tsx.tsx',
   'ejs': 'respons_ejs.ejs',
    # Backend va umumiy dasturlash
    'py': 'respons_py.py',  # PYTHON FAYLLARI TAHLIL QILINADI!
    'java': 'respons_java.java',
    'cs': 'respons_cs.cs',
    'cpp': 'respons_cpp.cpp',
    'c': 'respons_c.c',
    'rb': 'respons_rb.rb',
    'go': 'respons_go.go',
    'kt': 'respons_kt.kt',
    'rs': 'respons_rs.rs',
    'swift': 'respons_swift.swift',
    'dart': 'respons_dart.dart',
    'sh': 'respons_sh.sh',
    'pl': 'respons_pl.pl',
    'lua': 'respons_lua.lua',
    'r': 'respons_r.r',
    'bat': 'respons_bat.bat',
    'ps1': 'respons_ps1.ps1',
    'asm': 'respons_asm.asm',
    # Skriptlar va konfiguratsiyalar
    'json': 'respons_json.json',
    'xml': 'respons_xml.xml',
    'yml': 'respons_yml.yml',
    'yaml': 'respons_yaml.yaml',
    'toml': 'respons_toml.toml',
    'ini': 'respons_ini.ini',
    'env': 'respons_env.env',
    'conf': 'respons_conf.conf',
    'cfg': 'respons_cfg.cfg',
    # Mobil ilovalar
    'kt': 'respons_kt.kt',
    'swift': 'respons_swift.swift',
    # Ma'lumotlar bazasi bilan ishlaydigan fayllar
    'csv': 'respons_csv.csv',
    'tsv': 'respons_tsv.tsv',
    # Shell va tizim fayllari
    'sh': 'respons_sh.sh',
    'bat': 'respons_bat.bat',
    'ps1': 'respons_ps1.ps1',
    'cmd': 'respons_cmd.cmd',
    # Skriptlar va o`yin dvijoklari
    'lua': 'respons_lua.lua',
    'gd': 'respons_gd.gd',
    'scm': 'respons_scm.scm',
    'hx': 'respons_hx.hx',
    # Boshqa formatlar
    'md': 'respons_md.md',
    'txt': 'respons_txt.txt',
    'log': 'respons_log.log',
}

# SKIP QILINADIGAN PAPKALAR (FAQAT VENV VA UNGA O'XSHAGANLAR)
SKIP_FOLDERS = {
    'venv', 'env', '.env', 'node_modules', '.git', '__pycache__', 
    'dist', 'build', 'target', '.idea', '.vscode',
    'coverage', '.pytest_cache', '.mypy_cache', '.tox', 'htmlcov',
    'Lib', 'Scripts',  # Windows venv papkalari
    'bin', 'lib', 'include',  # Linux venv papkalari
    'site-packages', 'dist-packages'
}

# SKIP QILINADIGAN FAYLLAR (FAQAT O'ZI VA CHIQISH FAYLLARI)
SKIP_FILES = {
    'CodeAnalyzer.py',  # O'zini skip qilish
}

# Manba: Otaboyev Sardorbek tomonidan yaratildi
def print_banner():
    os.system('color 4' if os.name == 'nt' else '')
    project_name = "Code_Analyzer Pro"
    email = "prodevuzoff@gmail.com"
    telegram = "@otaboyev_sardorbek_blog_dev"
    github_repo = "https://github.com/otaboyevsardorbek1/CodeAnalyzer"

    ascii_banner = pyfiglet.figlet_format(project_name, font='slant')
    print(colored(ascii_banner, 'red'))
    print(colored(f"Email: {email}", 'blue'))
    print(colored(f"Telegram: {telegram}", 'cyan'))
    print(colored(f"GitHub: {github_repo}", 'yellow'))
    print(colored("-" * 60, 'white'))

def should_skip_path(path):
    """Berilgan yo'lni skip qilish kerakmi?"""
    path_parts = Path(path).parts
    
    # 1. VENV va unga o'xshagan papkalarni tekshirish
    for folder in SKIP_FOLDERS:
        if folder in path_parts:
            # Agar pathda 'venv' bo'lsa, skip qilish
            return True
    
    # 2. Fayl nomini tekshirish (faqat o'zini va chiqish fayllarini)
    if os.path.isfile(path):
        filename = os.path.basename(path)
        if filename in SKIP_FILES:
            return True
    
    return False

def count_files(root_folder):
    """Tahlil qilinadigan fayllar sonini hisoblash"""
    total = 0
    for root, dirs, files in os.walk(root_folder):
        # Skip papkalarni filtrash
        dirs[:] = [d for d in dirs if not should_skip_path(os.path.join(root, d))]
        
        for file in files:
            full_path = os.path.join(root, file)
            if should_skip_path(full_path):
                continue
            ext = file.split('.')[-1].lower()
            if ext in response_files:
                total += 1
    return total

def print_progress(current, total, bar_length=40):
    """Progress barni chiqarish"""
    if total == 0:
        return
    percent = current / total
    arrow = '█' * int(round(percent * bar_length))
    spaces = '░' * (bar_length - len(arrow))
    sys.stdout.write(f"\r[{colored(arrow, 'green')}{spaces}] {current}/{total} ({percent:.1%})")
    sys.stdout.flush()

def build_json_structure(root_folder):
    """JSON tuzish funksiyasi"""
    structure = {}
    existing_extensions = set()
    
    # Fayllarni sanash
    total_files = count_files(root_folder)
    processed = 0
    
    if total_files > 0:
        print(colored(f"\n📊 {total_files} ta fayl topildi. Tahlil boshlandi...", 'yellow'))
    else:
        print(colored(f"\n⚠️  Hech qanday fayl topilmadi!", 'yellow'))
        return structure, existing_extensions
    
    for root, dirs, files in os.walk(root_folder):
        # Skip papkalarni filtrash
        original_dirs = dirs.copy()
        dirs[:] = [d for d in dirs if not should_skip_path(os.path.join(root, d))]
        
        # Skip qilingan papkalarni ko'rsatish (agar xohlasangiz)
        skipped_dirs = set(original_dirs) - set(dirs)
        if skipped_dirs and processed == 0:
            print(colored(f"\n⏭️  Skip qilingan papkalar: {', '.join(skipped_dirs)}", 'yellow'))
        
        relative_path = os.path.relpath(root, root_folder)
        if relative_path == ".":
            relative_path = ""

        structure[relative_path] = {}
        for file in files:
            full_path = os.path.join(root, file)
            
            # Skip fayllarni filtrash
            if should_skip_path(full_path):
                continue
            
            file_ext = file.split('.')[-1].lower()
            if file_ext in response_files:
                existing_extensions.add(file_ext)
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    structure[relative_path][file] = content
                except Exception as e:
                    structure[relative_path][file] = f"Error reading file: {str(e)}"
                
                processed += 1
                print_progress(processed, total_files)
    
    print()  # Yangi qator
    return structure, existing_extensions

def write_responses(structure, output_folder):
    """Fayllarni turlar bo'yicha javob fayllariga yozish"""
    categorized_data = {ext: {} for ext in response_files.keys()}
    
    for folder, files in structure.items():
        for file, content in files.items():
            ext = file.split('.')[-1].lower()
            if ext in categorized_data:
                if folder not in categorized_data[ext]:
                    categorized_data[ext][folder] = {}
                categorized_data[ext][folder][file] = content
    
    saved_file_paths = []
    for ext, data in categorized_data.items():
        if data:
            output_file = os.path.join(output_folder, response_files[ext])
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    for folder, files in data.items():
                        for file, content in files.items():
                            f.write(f"File: {os.path.join(folder, file)}\n")
                            f.write(content + "\n\n")
                    saved_file_paths.append(output_file)
            except Exception as e:
                print(colored(f"❌ {output_file} yozishda xato: {e}", 'red'))
    
    return saved_file_paths

def main():
    """Asosiy dastur"""
    print_banner()
    
    try:
        print(colored("\n📁 LOYIHA PAPKASI", 'cyan', attrs=['bold']))
        print(colored("ℹ️  Loyihadagi barcha fayllar tahlil qilinadi, faqat:", 'white'))
        print(colored("   • venv, env, node_modules, .git kabi papkalar SKIP", 'yellow'))
        print(colored("   • CodeAnalyzer.py va respons_*.fayllar SKIP", 'yellow'))
        print(colored("   • Barcha Python fayllari TAHLIL QILINADI!", 'green', attrs=['bold']))
        
        root_folder = input(colored("\n➡️  Loyiha asosiy papkasini kiriting: ", 'green')).strip()
        
        if not root_folder:
            print(colored("\n❌ Dastur to'xtatildi!", 'red', attrs=['bold']))
            sys.exit()
            
        if not os.path.isdir(root_folder):
            print(colored(f"\n❌ '{root_folder}' papkasi mavjud emas!", 'red', attrs=['bold']))
            sys.exit(1)
        
        output_folder = os.path.join(root_folder, 'CodeAnalyzer_respons')
        
        print(colored(f"\n🔍 Tahlil qilinmoqda: {root_folder}", 'cyan'))
        
        # JSON tuzish
        json_structure, existing_extensions = build_json_structure(root_folder)
        
        # Mavjud kengaytmalarni chiqarish
        if existing_extensions:
            print(colored("\n📌 TOPILGAN KENGAYTMALAR:", 'cyan', attrs=['bold']))
            ext_list = sorted(existing_extensions)
            # Python'ni alohida ko'rsatish
            if 'py' in ext_list:
                print(colored(f"  • Python (.py) - TAHLIL QILINADI ✅", 'green'))
                ext_list.remove('py')
            for ext in ext_list:
                print(colored(f"  • {ext.upper()}", 'white'))
        else:
            print(colored("\n⚠️  Hech qanday mos fayl topilmadi!", 'yellow'))
            return
        
        # Natijalarni saqlash papkasini yaratish
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            print(colored(f"\n📁 Chiqish papkasi yaratildi: {output_folder}", 'green'))
        
        # JSON natijasini saqlash
        json_output_file = os.path.join(output_folder, 'project_structure.json')
        with open(json_output_file, 'w', encoding='utf-8') as f:
            json.dump(json_structure, f, indent=4, ensure_ascii=False)
        
        print(colored(f"\n📄 JSON fayl saqlandi: {json_output_file}", 'cyan'))
        
        # Javob fayllarini yozish
        print(colored("\n✍️  Javob fayllari yozilmoqda...", 'yellow'))
        saved_file_paths = write_responses(json_structure, output_folder)
        
        # Natijalarni ko'rsatish
        if saved_file_paths:
            print(colored("\n✅ TAYYORLANGAN FAYLLAR:", 'green', attrs=['bold']))
            unique_files = list(dict.fromkeys(saved_file_paths))
            for i, file_path in enumerate(unique_files, 1):
                file_name = os.path.basename(file_path)
                print(colored(f"  {i}. {file_name}", 'white'))
                print(colored(f"     📍 {file_path}", 'blue'))
            
            print(colored(f"\n🎉 JAMI {len(unique_files)} TA FAYL YARATILDI!", 'green', attrs=['bold']))
        else:
            print(colored("\n⚠️  Hech qanday fayl yaratilmadi!", 'yellow'))
    
    except KeyboardInterrupt:
        print(colored("\n\n⚠️  Dastur foydalanuvchi tomonidan to'xtatildi!", 'yellow'))
    except Exception as e:
        print(colored(f"\n❌ Kutilmagan xato: {e}", 'red'))
        import traceback
        traceback.print_exc()
    
    finally:
        print(colored("\n" + "="*60, 'white'))
        print(colored("✨ Tahlil yakunlandi!", 'cyan', attrs=['bold']))

if __name__ == "__main__":
    main()