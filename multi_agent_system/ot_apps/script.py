"""
Overtime Form Filling Module
Refactored for use as a tool in the multi-agent system
"""
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any
from ot_form_models import OTFormRequest, EmployeeInfo, OTEntry


# Template file path (relative to this script)
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'PWN-HRA-OTF-2F Overtime Form (Issue 1, Rev 0).xlsx')
OUTPUT_BASE_DIR = os.path.join(os.path.dirname(__file__))


def fill_ot_form(form_request: OTFormRequest) -> Dict[str, Any]:
    """
    Fill overtime form with provided data
    
    Args:
        form_request: OTFormRequest containing employee info and OT entries
        
    Returns:
        Dict with status, file_path, and download_url
    """
    try:
        # Validate template exists
        if not os.path.exists(TEMPLATE_PATH):
            return {
                "status": "error",
                "message": f"Template file not found at {TEMPLATE_PATH}"
            }
        
        # Load workbook
        wb = openpyxl.load_workbook(TEMPLATE_PATH)
        sheet = wb.active
        
        # Extract data
        emp = form_request.employee_info
        entries = form_request.ot_entries

        # Fill header info (corrected cell positions)
        # Merge cells for name to allow longer names
        sheet.merge_cells('B5:F5')
        sheet['B5'] = emp.name
        sheet['B6'] = emp.designation
        sheet['H5'] = emp.month
        sheet['I5'] = emp.year
        sheet['K5'] = emp.grade
        sheet['H6'] = emp.department

        # Fill overtime table (starts at row 14)
        start_row = 14
        for i, entry in enumerate(entries):
            current_row = start_row + i

            # Format date as dd-mmm-yy (e.g., "06-Dec-25")
            date_obj = datetime.strptime(entry.date, '%Y-%m-%d')
            formatted_date = date_obj.strftime('%d-%b-%y')

            sheet[f'A{current_row}'] = formatted_date
            sheet[f'B{current_row}'] = entry.start_time
            sheet[f'C{current_row}'] = entry.end_time
            sheet[f'D{current_row}'] = entry.work_schedule
            sheet[f'G{current_row}'] = entry.reason

        # Insert signature if provided
        if emp.signature_path and os.path.exists(emp.signature_path):
            try:
                # Load signature image
                img = XLImage(emp.signature_path)

                # Resize to fit in cells A50:B52 (approximately 2 columns x 3 rows)
                # Adjust size as needed - typical cell width ~64 pixels, height ~20 pixels
                img.width = 128   # 2 columns
                img.height = 60   # 3 rows

                # Position at A50
                sheet.add_image(img, 'A50')
            except Exception as e:
                print(f"Warning: Could not insert signature image: {str(e)}")

        # Create output directory structure: /ot_apps/{name}/{date}/
        # Sanitize name for directory
        safe_name = "".join(c for c in emp.name if c.isalnum() or c in (' ', '-', '_')).strip().replace(' ', '_')
        date_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        output_dir = os.path.join(OUTPUT_BASE_DIR, safe_name, date_str)
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename
        filename = f"OT_Form_{emp.month:02d}_{emp.year}.xlsx"
        output_path = os.path.join(output_dir, filename)
        
        # Save file
        wb.save(output_path)
        
        # Generate download URL (assuming server runs on localhost:8082)
        # Relative path from multi_agent_system directory
        relative_path = os.path.relpath(output_path, os.path.dirname(OUTPUT_BASE_DIR))
        download_url = f"http://localhost:8082/files/{relative_path.replace(os.sep, '/')}"
        
        return {
            "status": "success",
            "message": f"Overtime form created successfully for {emp.name}",
            "file_path": output_path,
            "download_url": download_url,
            "entries_count": len(entries)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error creating overtime form: {str(e)}"
        }


# Keep original script functionality for standalone testing
if __name__ == "__main__":
    from ot_form_models import OTFormRequest, EmployeeInfo, OTEntry
    
    # Test data
    test_request = OTFormRequest(
        employee_info=EmployeeInfo(
            name="Muhammad Husayn Irfan bin Mohammad Noor",
            designation="Simulator Support Engineer",
            department="Technical",
            grade="E4",
            month=11,
            year=2025
        ),
        ot_entries=[
            OTEntry(
                date="2025-11-06",
                start_time="21:00",
                end_time="09:00",
                work_schedule="Rest Day",
                reason="Replace Luqman"
            )
        ]
    )
    
    result = fill_ot_form(test_request)
    print(result)