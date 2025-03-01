#!/usr/bin/env python3
import os
import random
import string
import argparse
import time
import json
import sys
import shutil

def generate_random_name(length=10, use_letters=True, use_digits=True, use_special=False):
    """Generate a random string of fixed length."""
    chars = ""
    if use_letters:
        chars += string.ascii_lowercase + string.ascii_uppercase
    if use_digits:
        chars += string.digits
    if use_special:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    
    # Ensure we have some characters to choose from
    if not chars:
        chars = string.ascii_lowercase + string.digits
    
    return ''.join(random.choice(chars) for _ in range(length))

def should_exclude_file(filename, script_path, options):
    """
    Determine if a file should be excluded from renaming based on options.
    
    Args:
        filename (str): Full path to the file
        script_path (str): Full path to this script
        options (dict): Dictionary containing exclusion options
        
    Returns:
        bool: True if the file should be excluded, False otherwise
    """
    # Get just the filename without path
    base_filename = os.path.basename(filename)
    
    # Exclude the script itself
    if options.get('exclude_script', True) and os.path.abspath(filename) == script_path:
        return True
        
    # Check for excluded extensions
    _, extension = os.path.splitext(base_filename)
    if extension.lower() in options.get('exclude_extensions', []):
        return True
        
    # Check for excluded patterns
    if options.get('exclude_patterns'):
        for pattern in options['exclude_patterns']:
            if pattern in base_filename:
                return True
                
    return False

def is_long_path(path):
    """Check if a path is close to or exceeds the Windows path length limit."""
    # Windows has a 260 character path length limitation by default
    # We use a safety margin to prevent issues
    return len(path) > 240

def safe_rename(old_path, new_path):
    """
    Safely rename a file, handling potential Windows long path issues.
    
    Args:
        old_path (str): Original file path
        new_path (str): New file path
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Try direct renaming first
        os.rename(old_path, new_path)
        return True
    except FileNotFoundError:
        # For very long paths on Windows, we might need to use alternate methods
        try:
            # Try with \\?\ prefix for Windows long paths
            if sys.platform == 'win32':
                # This works on modern Windows to handle long paths
                new_old_path = "\\\\?\\" + os.path.abspath(old_path)
                new_new_path = "\\\\?\\" + os.path.abspath(new_path)
                os.rename(new_old_path, new_new_path)
                return True
            else:
                # Not a Windows system, so this shouldn't happen
                return False
        except Exception:
            # If all else fails, try copy and delete approach
            try:
                shutil.copy2(old_path, new_path)
                os.remove(old_path)
                return True
            except Exception:
                return False
    except Exception:
        return False

def rename_files_recursively(root_folder, options):
    """
    Recursively rename all files in the given folder and its subfolders.
    
    Args:
        root_folder (str): The root folder to start from
        options (dict): Dictionary containing various options for renaming
        
    Returns:
        dict: Statistics about the renaming operation
    """
    # Check if the folder exists
    if not os.path.isdir(root_folder):
        raise ValueError(f"The specified path '{root_folder}' is not a valid directory")
    
    # Get the full path to this script
    script_path = os.path.abspath(__file__)
    
    # Dictionary to store the mapping of old names to new names
    renamed_files = {}
    
    # Set to keep track of already used random names (per directory)
    used_names_by_dir = {}
    
    # Prepare log file if needed
    if options.get('create_log', True):
        log_data = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'root_folder': os.path.abspath(root_folder),
            'files': {}
        }
    
    # Initialize counters for statistics
    counter = {'total': 0, 'renamed': 0, 'skipped': 0, 'errors': 0}
    
    # Enable long path support on Windows if possible
    if sys.platform == 'win32':
        try:
            # This requires Python 3.6+ and Windows 10+
            print("Enabling long path support for Windows...")
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\FileSystem', 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, 'LongPathsEnabled', 0, winreg.REG_DWORD, 1)
            print("Long path support enabled.")
        except Exception as e:
            print(f"Note: Could not enable Windows long path support. Error: {e}")
            print("Using alternative method for long paths.")
    
    # Walk through directory tree
    for current_dir, subdirs, files in os.walk(root_folder):
        rel_dir = os.path.relpath(current_dir, root_folder)
        dir_display = rel_dir if rel_dir != '.' else 'root directory'
        print(f"\nProcessing {dir_display}...")
        
        # Create a set for used names in this directory
        if current_dir not in used_names_by_dir:
            used_names_by_dir[current_dir] = set()
        
        # Process files in the current directory
        for filename in files:
            counter['total'] += 1
            file_path = os.path.join(current_dir, filename)
            
            # Check if the file should be excluded
            if should_exclude_file(file_path, script_path, options):
                status = "Skipping"
                new_name = "[excluded]"
                counter['skipped'] += 1
                print(f"{status}: {filename} {new_name}")
                continue
            
            # Get the file extension
            name_part, extension = os.path.splitext(filename)
            
            # Generate a unique random name
            while True:
                new_name = generate_random_name(
                    length=options.get('name_length', 10),
                    use_letters=options.get('use_letters', True),
                    use_digits=options.get('use_digits', True),
                    use_special=options.get('use_special', False)
                ) + extension
                
                if new_name not in used_names_by_dir[current_dir]:
                    used_names_by_dir[current_dir].add(new_name)
                    break
            
            # Full paths for old and new names
            old_path = os.path.join(current_dir, filename)
            new_path = os.path.join(current_dir, new_name)
            
            # Check for potential long path issues on Windows
            if is_long_path(old_path) or is_long_path(new_path):
                print(f"Warning: Path is very long and may cause issues: {old_path}")
            
            # Only perform actual renaming if not in dry run mode
            success = True
            if not options.get('dry_run', False):
                success = safe_rename(old_path, new_path)
                if success:
                    status = "Renamed"
                    counter['renamed'] += 1
                else:
                    status = "ERROR renaming"
                    counter['errors'] += 1
                    print(f"Failed to rename: {old_path}")
                    print(f"Possible issues: Path too long or file in use")
                    continue
            else:
                status = "Would rename"
            
            # Store the mapping
            rel_path = os.path.relpath(old_path, root_folder)
            rel_new_path = os.path.relpath(new_path, root_folder)
            renamed_files[rel_path] = rel_new_path
            print(f"{status}: {rel_path} -> {rel_new_path}")
            
            # Add to log data
            if options.get('create_log', True):
                log_data['files'][rel_path] = rel_new_path
    
    # Save log file if needed
    if options.get('create_log', True) and renamed_files and not options.get('dry_run', False):
        log_filename = os.path.join(root_folder, f"rename_log_{time.strftime('%Y%m%d_%H%M%S')}.json")
        with open(log_filename, 'w') as f:
            json.dump(log_data, f, indent=2)
        print(f"\nRename log saved to: {log_filename}")
    
    # Print summary
    print(f"\nSummary:")
    print(f"  Total files found: {counter['total']}")
    print(f"  Files renamed: {counter['renamed']}")
    print(f"  Files skipped: {counter['skipped']}")
    print(f"  Files with errors: {counter['errors']}")
    
    return counter

if __name__ == "__main__":
    # Set up command-line argument parsing
    parser = argparse.ArgumentParser(description="Recursively rename all files (not folders) to random names")
    parser.add_argument("--folder", help="Path to the folder containing files to rename (default: current directory)")
    parser.add_argument("--length", type=int, default=10, help="Length of random names (default: 10)")
    parser.add_argument("--no-letters", action="store_true", help="Don't use letters in random names")
    parser.add_argument("--no-digits", action="store_true", help="Don't use digits in random names")
    parser.add_argument("--special", action="store_true", help="Include special characters in random names")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be renamed without actually renaming")
    parser.add_argument("--no-log", action="store_true", help="Don't create a log file of the renaming")
    parser.add_argument("--include-script", action="store_true", help="Allow renaming of this script itself (not recommended)")
    parser.add_argument("--exclude", action="append", help="Exclude files containing these patterns (can be used multiple times)")
    parser.add_argument("--exclude-ext", action="append", help="Exclude files with these extensions (can be used multiple times)")
    parser.add_argument("--max-depth", type=int, help="Maximum depth of subdirectories to process (default: unlimited)")
    parser.add_argument("--short-name", action="store_true", help="Use shorter random names (5 chars) for long paths")
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        # If no folder is specified, use the directory where the script is located
        if args.folder:
            folder_path = args.folder
        else:
            folder_path = os.path.dirname(os.path.abspath(__file__)) or "."
            print(f"Working on the current directory: {folder_path}")
        
        # Prepare options dictionary
        options = {
            'name_length': args.length,
            'use_letters': not args.no_letters,
            'use_digits': not args.no_digits,
            'use_special': args.special,
            'dry_run': args.dry_run,
            'create_log': not args.no_log,
            'exclude_script': not args.include_script,
            'max_depth': args.max_depth,
            'short_name': args.short_name
        }
        
        # Add exclude patterns
        if args.exclude:
            options['exclude_patterns'] = args.exclude
        
        # Add exclude extensions
        if args.exclude_ext:
            options['exclude_extensions'] = [f".{ext.lstrip('.')}" for ext in args.exclude_ext]
        
        # Print mode info
        if options['dry_run']:
            print("Running in DRY RUN mode. No files will be actually renamed.")
        
        # Print script exclusion info
        if options['exclude_script']:
            print(f"Note: This script will be excluded from renaming.")
        
        # Call the function with the provided options
        rename_files_recursively(folder_path, options)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()