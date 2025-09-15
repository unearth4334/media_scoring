"""HTML export functionality for mining test results."""

from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import os

from ..models.media_file import MediaFile


def export_mining_test_results_html(media_files: List[MediaFile], media_dir: Path, output_path: Path) -> bool:
    """
    Export media files with full metadata to an HTML file.
    
    Args:
        media_files: List of MediaFile objects to export
        media_dir: Base media directory (for calculating relative paths)
        output_path: Path where HTML file should be written
        
    Returns:
        True if export successful, False otherwise
    """
    try:
        html_content = generate_mining_test_results_html(media_files, media_dir)
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write HTML file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return True
        
    except Exception as e:
        print(f"Error exporting HTML: {e}")
        return False


def generate_mining_test_results_html(media_files: List[MediaFile], media_dir: Path) -> str:
    """Generate HTML content for mining test results."""
    
    # Convert absolute media_dir to string for comparison
    media_dir_str = str(media_dir.resolve())
    
    # Calculate stats
    total_files = len(media_files)
    scored_files = len([f for f in media_files if f.score is not None and f.score > 0])
    avg_score = sum(f.score or 0 for f in media_files) / total_files if total_files > 0 else 0
    
    # Group files by score for overview
    score_counts = {}
    for f in media_files:
        score = f.score or 0
        score_counts[score] = score_counts.get(score, 0) + 1
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mining Test Results - Media Files Export</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                color: #333;
            }}
            
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 10px;
                margin-bottom: 30px;
                text-align: center;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            }}
            
            .header h1 {{
                margin: 0 0 10px 0;
                font-size: 2.5em;
                font-weight: 300;
            }}
            
            .header .subtitle {{
                font-size: 1.1em;
                opacity: 0.9;
                margin: 5px 0;
            }}
            
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            
            .stat-card {{
                background: white;
                padding: 20px;
                border-radius: 8px;
                text-align: center;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                border-left: 4px solid #667eea;
            }}
            
            .stat-value {{
                font-size: 2em;
                font-weight: bold;
                color: #667eea;
                margin-bottom: 5px;
            }}
            
            .stat-label {{
                color: #666;
                font-size: 0.9em;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            .table-container {{
                background: white;
                border-radius: 10px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                overflow: hidden;
            }}
            
            .table-header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                font-size: 1.2em;
                font-weight: 500;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9em;
            }}
            
            th, td {{
                padding: 12px 8px;
                text-align: left;
                border-bottom: 1px solid #e0e0e0;
                vertical-align: top;
            }}
            
            th {{
                background-color: #f8f9fa;
                font-weight: 600;
                color: #444;
                position: sticky;
                top: 0;
                z-index: 10;
            }}
            
            tr:hover {{
                background-color: #f8f9ff;
            }}
            
            .score-badge {{
                display: inline-block;
                padding: 4px 8px;
                border-radius: 15px;
                font-weight: bold;
                font-size: 0.8em;
                min-width: 30px;
                text-align: center;
            }}
            
            .score-0 {{ background: #e9ecef; color: #6c757d; }}
            .score-1 {{ background: #ffeaa7; color: #d63031; }}
            .score-2 {{ background: #fdcb6e; color: #e17055; }}
            .score-3 {{ background: #a29bfe; color: #6c5ce7; }}
            .score-4 {{ background: #74b9ff; color: #0984e3; }}
            .score-5 {{ background: #55a3ff; color: #0055ff; }}
            .score-reject {{ background: #ff6b6b; color: white; }}
            
            .filepath {{
                font-family: 'Courier New', monospace;
                font-size: 0.85em;
                background: #f1f3f4;
                padding: 2px 6px;
                border-radius: 3px;
                word-break: break-all;
            }}
            
            .param-value {{
                font-family: 'Courier New', monospace;
                font-size: 0.85em;
                max-width: 150px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            
            .dimensions {{
                color: #666;
                font-size: 0.85em;
            }}
            
            .null-value {{
                color: #999;
                font-style: italic;
            }}
            
            .export-info {{
                background: #e3f2fd;
                border-left: 4px solid #2196f3;
                padding: 15px;
                margin: 20px 0;
                border-radius: 0 5px 5px 0;
            }}
            
            .footer {{
                text-align: center;
                margin-top: 40px;
                padding: 20px;
                color: #666;
                border-top: 1px solid #e0e0e0;
            }}
            
            @media (max-width: 768px) {{
                .stats {{
                    grid-template-columns: 1fr;
                }}
                
                table {{
                    font-size: 0.8em;
                }}
                
                th, td {{
                    padding: 8px 4px;
                }}
                
                .param-value {{
                    max-width: 100px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎬 Mining Test Results</h1>
            <div class="subtitle">Media Files Export Report</div>
            <div class="subtitle">Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>
        </div>
        
        <div class="export-info">
            <strong>Export Details:</strong><br>
            Media Directory: <code>{media_dir_str}</code><br>
            Export Time: {datetime.now().isoformat()}<br>
            Total Files: {total_files}
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{total_files}</div>
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{scored_files}</div>
                <div class="stat-label">Scored Files</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{avg_score:.1f}</div>
                <div class="stat-label">Average Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len([f for f in media_files if f.generation_params])}</div>
                <div class="stat-label">With Generation Data</div>
            </div>
        </div>
        
        <div class="table-container">
            <div class="table-header">
                📊 Detailed Media File Analysis
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Filename</th>
                        <th>Filepath</th>
                        <th>Score</th>
                        <th>Dimensions</th>
                        <th>Size (bytes)</th>
                        <th>Steps</th>
                        <th>Sampler</th>
                        <th>Schedule Type</th>
                        <th>CFG Scale</th>
                        <th>Seed</th>
                        <th>Model Name</th>
                        <th>Model Hash</th>
                        <th>Denoising Strength</th>
                        <th>Hires Module 1</th>
                        <th>Hires CFG Scale</th>
                        <th>Hires Upscale</th>
                        <th>Hires Upscaler</th>
                        <th>DynThres Enabled</th>
                        <th>DynThres Mimic Scale</th>
                        <th>DynThres Threshold %</th>
                        <th>DynThres Mimic Mode</th>
                        <th>DynThres Mimic Scale Min</th>
                        <th>DynThres CFG Mode</th>
                        <th>DynThres CFG Scale Min</th>
                        <th>DynThres Sched Val</th>
                        <th>DynThres Separate Channels</th>
                        <th>DynThres Scaling Start</th>
                        <th>DynThres Variability</th>
                        <th>DynThres Interpolate Phi</th>
                        <th>Version</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    # Add rows for each media file
    for file in media_files:
        score_class = "score-reject" if file.score == -1 else f"score-{file.score or 0}"
        score_display = "R" if file.score == -1 else str(file.score or 0)
        
        # Get generation parameters
        gp = file.generation_params
        
        def format_param(value, param_type="str"):
            """Format parameter value for display."""
            if value is None:
                return '<span class="null-value">—</span>'
            
            if param_type == "bool":
                return "✓" if value else "✗"
            elif param_type == "float":
                return f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
            else:
                return str(value)
        
        dimensions = ""
        if file.width and file.height:
            dimensions = f"{file.width}×{file.height}"
        
        html += f"""
                    <tr>
                        <td><strong>{file.filename}</strong></td>
                        <td><span class="filepath">{file.filepath}</span></td>
                        <td><span class="score-badge {score_class}">{score_display}</span></td>
                        <td class="dimensions">{dimensions}</td>
                        <td>{file.file_size or ''}</td>
                        <td class="param-value">{format_param(gp.steps if gp else None)}</td>
                        <td class="param-value">{format_param(gp.sampler if gp else None)}</td>
                        <td class="param-value">{format_param(gp.schedule_type if gp else None)}</td>
                        <td class="param-value">{format_param(gp.cfg_scale if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.seed if gp else None)}</td>
                        <td class="param-value">{format_param(gp.model_name if gp else None)}</td>
                        <td class="param-value">{format_param(gp.model_hash if gp else None)}</td>
                        <td class="param-value">{format_param(gp.denoising_strength if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.hires_module_1 if gp else None)}</td>
                        <td class="param-value">{format_param(gp.hires_cfg_scale if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.hires_upscale if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.hires_upscaler if gp else None)}</td>
                        <td class="param-value">{format_param(gp.dynthres_enabled if gp else None, "bool")}</td>
                        <td class="param-value">{format_param(gp.dynthres_mimic_scale if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.dynthres_threshold_percentile if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.dynthres_mimic_mode if gp else None)}</td>
                        <td class="param-value">{format_param(gp.dynthres_mimic_scale_min if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.dynthres_cfg_mode if gp else None)}</td>
                        <td class="param-value">{format_param(gp.dynthres_cfg_scale_min if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.dynthres_sched_val if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.dynthres_separate_feature_channels if gp else None, "bool")}</td>
                        <td class="param-value">{format_param(gp.dynthres_scaling_startpoint if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.dynthres_variability_measure if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.dynthres_interpolate_phi if gp else None, "float")}</td>
                        <td class="param-value">{format_param(gp.version if gp else None)}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Generated by Media Scoring Application</p>
            <p>This report contains detailed analysis of media files including generation parameters extracted from image metadata.</p>
        </div>
        
        <script>
            // Add some interactive features
            document.addEventListener('DOMContentLoaded', function() {
                // Make table sortable (basic functionality)
                const headers = document.querySelectorAll('th');
                headers.forEach(header => {
                    header.style.cursor = 'pointer';
                    header.addEventListener('click', function() {
                        // Simple visual feedback for sorting
                        this.style.backgroundColor = '#e3f2fd';
                        setTimeout(() => {
                            this.style.backgroundColor = '#f8f9fa';
                        }, 200);
                    });
                });
                
                // Add tooltips for truncated values
                const paramValues = document.querySelectorAll('.param-value');
                paramValues.forEach(cell => {
                    if (cell.scrollWidth > cell.offsetWidth) {
                        cell.title = cell.textContent;
                    }
                });
            });
        </script>
    </body>
    </html>
    """
    
    return html