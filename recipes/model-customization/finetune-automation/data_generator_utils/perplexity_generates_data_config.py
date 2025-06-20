#!/usr/bin/env python3
"""
Enhanced Perplexity API-based YAML Configuration Generator
Creates rich, diverse synthetic data configurations with 50+ attributes and high cardinality.
"""

import os
import sys
import requests
import json
import yaml
import io
import codecs
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import ruamel.yaml

# Handle emoji in all environments safely
def safe_print(text):
    """Print text safely in any environment, handling emojis properly."""
    try:
        print(text)
    except UnicodeEncodeError:
        # If normal print fails, try alternative methods
        try:
            # For Windows cmd/powershell when called from another process
            if sys.platform == 'win32':
                # Replace emojis with plain text versions
                text = (text.replace('🎯', '[TARGET] ')
                         .replace('📋', '[LIST] ')
                         .replace('🔍', '[SEARCH] ')
                         .replace('🧹', '[CLEAN] ')
                         .replace('📊', '[STATS] ')
                         .replace('✅', '[OK] ')
                         .replace('🎉', '[SUCCESS] ')
                         .replace('📁', '[FILE] ')
                         .replace('🏷️', '[TAG] ')
                         .replace('🏆', '[TROPHY] ')
                         .replace('📚', '[SOURCES] ')
                         .replace('🚀', '[ROCKET] ')
                         .replace('❌', '[ERROR] '))
                print(text)
            else:
                # For Unix systems, try UTF-8 encoding
                print(text.encode('utf-8').decode(sys.stdout.encoding))
        except:
            # Last resort: remove emojis
            import re
            text = re.sub(r'[^\x00-\x7F]+', '', text)
            print(text)

load_dotenv()

# Load configuration from config.yaml
def load_config():
    """Load the config.yaml file."""
    yaml_handler = ruamel.yaml.YAML()
    yaml_handler.preserve_quotes = True
    
    try:
        # Get path to config.yaml in parent directory since we're now in data_generator_utils
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
        with open(config_path, "r") as f:
            return yaml_handler.load(f)
    except Exception as e:
        print(f"Error loading config.yaml: {e}")
        return {}

class EnhancedUseCaseGenerator:
    def __init__(self):
        self.api_url = "https://api.perplexity.ai/chat/completions"
        
        # Get API key from config.yaml, fallback to environment variable if not in config
        config = load_config()
        self.api_key = config.get("perplexity_api_key") or os.getenv("PERPLEXITY_API_KEY", "")
        
        if not self.api_key or self.api_key == "null":
            safe_print("❌ Perplexity API key not found in config.yaml or environment variables!")
            safe_print("Please add your API key to config.yaml or set the PERPLEXITY_API_KEY environment variable.")
            safe_print("Continuing with empty API key, but API calls will fail.")
        
    def load_instructions(self, instructions_file: str) -> str:
        """Load enhanced instructions from file."""
        try:
            with open(instructions_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Instructions file not found: {instructions_file}")
    
    def create_enhanced_prompt(self, instructions: str, domain: str) -> str:
        """Create a comprehensive prompt emphasizing richness and diversity."""
        prompt = f"""
You are an expert data architect and domain specialist with deep knowledge of {domain}. Your task is to create an exceptionally rich and diverse YAML configuration file for synthetic data generation.

CRITICAL OUTPUT REQUIREMENT:
- Provide ONLY the YAML configuration
- NO explanatory text before or after the YAML
- NO markdown formatting
- NO comments outside the YAML structure
- Start directly with "domain_name:" and end with the output section

CRITICAL REQUIREMENTS - YOU MUST ACHIEVE ALL OF THESE:
✅ CREATE 4-6 ENTITIES (Primary + Supporting + Reference + Historical)
✅ PRIMARY ENTITY: 15-25 attributes minimum
✅ TOTAL ATTRIBUTES: 50+ across all entities
✅ HIGH-CARDINALITY CATEGORICALS: At least 5 fields with 10-15+ categories each
✅ MULTIPLE LIST FIELDS: 3+ with varying min/max lengths (0-12 range)
✅ TEMPORAL COMPLEXITY: Multiple datetime fields with different ranges
✅ CULTURAL/GEOGRAPHIC DIVERSITY: Rich demographic categorizations
✅ BUSINESS WORKFLOW STATES: Complex status hierarchies
✅ QUANTITATIVE RICHNESS: Multiple numeric scales and measurement types
✅ RICH USER TEMPLATE: Use 15+ field placeholders
✅ DISPLAY NAME: Include a human-readable display_name field for web UI
✅ COMPLETE FINE_TUNING_TASK SECTION: This is mandatory

MANDATORY YAML STRUCTURE - OUTPUT EXACTLY THIS FORMAT:
domain_name: [snake_case_domain_name]
display_name: "[Human-readable name for web UI]"
description: [Brief description of the use case]

entities:
  - name: [EntityName]
    description: [Entity description]
    attributes:
      - name: [field_name]
        type: [field_type]
        [additional_constraints]
        description: [Field description]

relationships:
  - from: [SourceEntity]
    to: [TargetEntity]
    type: [relationship_type]
    description: [Relationship description]

fine_tuning_task:
  task_type: text_generation
  system_prompt: "[Domain-specific system prompt]"
  user_template: |
    [Multi-line template with 15+ {{field_name}} placeholders]
  primary_entity: [MainEntity]

output_format: llama_chat
metadata_fields: [list_of_key_fields]

output:
  format: jsonl
  directory: usecase_data/[domain_name]

ENHANCED INSTRUCTIONS:
{instructions}

DOMAIN FOCUS: {domain}

OUTPUT ONLY THE YAML CONFIGURATION - NO OTHER TEXT OR EXPLANATIONS.
"""
        return prompt

    def create_prompt(self, instructions: str, domain: str) -> str:
        """Create a comprehensive prompt combining instructions and domain."""
        return self.create_enhanced_prompt(instructions, domain)
    
    def call_perplexity_api(self, prompt: str, domain: str) -> tuple[str, List[str]]:
        """Enhanced API call with domain-specific search filters."""
        
        # Domain-specific search filters for better research
        domain_filters = {
            "enterprise_sales": ["salesforce.com", "hubspot.com", "pipedrive.com", "gartner.com", "forrester.com"],
            "healthcare": ["hl7.org", "fhir.org", "cms.gov", "who.int", "epic.com"],
            "finance": ["sec.gov", "swift.com", "iso20022.org", "finra.org", "bis.org"],
            "education": ["ed.gov", "canvas.instructure.com", "blackboard.com", "moodle.org"],
            "retail": ["nrf.com", "shopify.com", "magento.com", "woocommerce.com"],
            "manufacturing": ["iso.org", "sap.com", "oracle.com", "siemens.com"],
            "default": ["github.com", "stackoverflow.com", "kaggle.com", "wikipedia.org", "iso.org"]
        }
        
        search_filter = domain_filters.get(domain.lower().replace(" ", "_"), domain_filters["default"])
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "sonar-pro",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert data architect and domain specialist. You conduct thorough research on industry standards, regulatory requirements, and best practices before creating comprehensive synthetic data configurations. You always exceed minimum requirements and create exceptionally rich, diverse datasets."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.1,  # Very low for consistent, structured output
            "max_tokens": 6000,   # Increased for rich configurations
            "return_citations": True,
            "search_domain_filter": search_filter,
            "search_recency_filter": "month"  # Recent information
        }
        
        try:
            response = requests.post(self.api_url, headers=headers, json=data, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            content = response_data["choices"][0]["message"]["content"]
            citations = response_data.get("citations", [])
            
            return content, citations
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error calling Perplexity API: {str(e)}")
        except KeyError as e:
            if "401 Unauthorized" in response.text and not self.api_key:
                raise Exception("Perplexity API call failed: 401 Unauthorized. Please provide a valid API key in config.yaml.")
            else:
                raise Exception(f"Perplexity API call failed: {response.status_code} - {response.text}")
    
    def extract_yaml_content(self, content: str) -> str:
        """Enhanced YAML extraction with multiple format support."""
        # Handle various markdown formats - Fixed version
        yaml_markers = [
            ("```yaml", "```"),
            ("```YAML", "```"),
            ("```", "```"),
            ("``````yaml", "``````"),
            ("``````YAML", "``````"),
            ("``````", "``````")
        ]
        
        for start_marker, end_marker in yaml_markers:
            if start_marker in content:
                lines = content.split('\n')
                yaml_lines = []
                in_yaml_block = False
                
                for line in lines:
                    if line.strip().startswith(start_marker):
                        in_yaml_block = True
                        continue
                    elif line.strip().startswith(end_marker) and in_yaml_block:
                        break
                    elif in_yaml_block:
                        yaml_lines.append(line)
                
                if yaml_lines:
                    return "\n".join(yaml_lines)

        # If no code blocks, try to find YAML structure
        lines = content.split('\n')
        yaml_start = -1
        yaml_end = -1

        for i, line in enumerate(lines):
            if line.strip().startswith('domain_name:'):
                yaml_start = i
                break

        if yaml_start >= 0:
            # Find the end of YAML content (stop at explanatory text)
            for i in range(yaml_start, len(lines)):
                line = lines[i].strip()
                # Stop if we hit explanatory text or comments that aren't YAML
                if (line and 
                    not line.startswith('#') and 
                    not ':' in line and 
                    not line.startswith('-') and 
                    not line.startswith(' ') and
                    len(line) > 50):  # Long sentences are likely explanatory text
                    yaml_end = i
                    break
            
            if yaml_end > yaml_start:
                return "\n".join(lines[yaml_start:yaml_end])
            else:
                return "\n".join(lines[yaml_start:])

        return content.strip()
            
    def validate_enhanced_requirements(self, yaml_content: str) -> Dict[str, Any]:
        """Comprehensive validation against enhanced requirements."""
        try:
            config = yaml.safe_load(yaml_content)
            
            validation = {
                "total_attributes": 0,
                "entities_count": len(config.get('entities', [])),
                "high_cardinality_fields": 0,
                "list_fields": 0,
                "temporal_fields": 0,
                "numeric_fields": 0,
                "primary_entity_attributes": 0,
                "template_placeholders": 0,
                "has_display_name": bool(config.get('display_name')),
                "issues": [],
                "passed": True
            }
            
            # Count attributes and field types
            for entity in config.get('entities', []):
                attributes = entity.get('attributes', [])
                validation["total_attributes"] += len(attributes)
                
                # Check if this is likely the primary entity (most attributes)
                if len(attributes) > validation["primary_entity_attributes"]:
                    validation["primary_entity_attributes"] = len(attributes)
                
                for attr in attributes:
                    field_type = attr.get('type', '')
                    
                    if field_type == 'categorical':
                        categories = attr.get('categories', [])
                        if len(categories) >= 10:
                            validation["high_cardinality_fields"] += 1
                    
                    elif field_type == 'list':
                        validation["list_fields"] += 1
                    
                    elif field_type in ['datetime', 'date']:
                        validation["temporal_fields"] += 1
                    
                    elif field_type in ['integer', 'float']:
                        validation["numeric_fields"] += 1
            
            # Count template placeholders
            user_template = config.get('fine_tuning_task', {}).get('user_template', '')
            validation["template_placeholders"] = user_template.count('{')
            
            # Validate requirements
            if validation["total_attributes"] < 50:
                validation["issues"].append(f"Only {validation['total_attributes']} total attributes, need 50+")
                validation["passed"] = False
            
            if validation["entities_count"] < 4:
                validation["issues"].append(f"Only {validation['entities_count']} entities, need 4-6")
                validation["passed"] = False
            
            if validation["primary_entity_attributes"] < 15:
                validation["issues"].append(f"Primary entity has only {validation['primary_entity_attributes']} attributes, need 15-25")
                validation["passed"] = False
            
            if validation["high_cardinality_fields"] < 5:
                validation["issues"].append(f"Only {validation['high_cardinality_fields']} high-cardinality fields, need 5+")
                validation["passed"] = False
            
            if validation["list_fields"] < 3:
                validation["issues"].append(f"Only {validation['list_fields']} list fields, need 3+")
                validation["passed"] = False
            
            if validation["template_placeholders"] < 15:
                validation["issues"].append(f"Only {validation['template_placeholders']} template placeholders, need 15+")
                validation["passed"] = False
            
            # Validate display_name
            if not config.get('display_name'):
                validation["issues"].append("Missing display_name field for web UI")
                validation["passed"] = False
            elif len(config.get('display_name', '')) < 5:
                validation["issues"].append("display_name too short, should be descriptive")
                validation["passed"] = False
            
            return validation
        
        except Exception as e:
            return {"error": str(e), "passed": False}
    
    def save_enhanced_yaml(self, content: str, domain: str, validation: Dict[str, Any], 
                      output_dir: str = "data_gen_configs") -> str:
        """Save YAML with enhanced metadata."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    
        # Parse the YAML to get display_name
        try:
            config = yaml.safe_load(content)
            display_name = config.get('display_name', 'Unknown')
        except:
            display_name = 'Unknown'
    
        # Clean domain name for filename
        clean_domain = domain.lower().replace(' ', '_').replace('and', '').replace('__', '_').strip('_')
        filename = f"{clean_domain}.yaml"
        file_path = Path(output_dir) / filename
    
        # Add metadata header as comment
        header = f"""# Enhanced Synthetic Data Configuration
# Domain: {domain}
# Display Name: {display_name}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
# Total Attributes: {validation.get('total_attributes', 'Unknown')}
# Entities: {validation.get('entities_count', 'Unknown')}
# Primary Entity Attributes: {validation.get('primary_entity_attributes', 'Unknown')}
# High-Cardinality Fields: {validation.get('high_cardinality_fields', 'Unknown')}
# List Fields: {validation.get('list_fields', 'Unknown')}
# Temporal Fields: {validation.get('temporal_fields', 'Unknown')}
# Numeric Fields: {validation.get('numeric_fields', 'Unknown')}
# Template Placeholders: {validation.get('template_placeholders', 'Unknown')}
# Validation: {'PASSED' if validation.get('passed', False) else 'FAILED'}

"""
    
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(header + content)
    
        return str(file_path)
    
    def generate_enhanced_use_case(self, domain: str, instructions_file: str, 
                                  max_retries: int = 3) -> Dict[str, Any]:
        """Generate enhanced use case with validation and retry logic."""
        safe_print(f"🎯 Generating ENHANCED use case for domain: {domain}")
        safe_print("📋 Loading enhanced instructions...")
        
        instructions = self.load_instructions(instructions_file)
        
        for attempt in range(max_retries):
            try:
                safe_print(f"🔍 Attempt {attempt + 1}: Calling Perplexity API for deep research...")
                
                prompt = self.create_enhanced_prompt(instructions, domain)
                content, citations = self.call_perplexity_api(prompt, domain)
                
                safe_print("🧹 Extracting and validating YAML...")
                yaml_content = self.extract_yaml_content(content)
                
                # Validate YAML syntax
                try:
                    yaml.safe_load(yaml_content)
                except yaml.YAMLError as e:
                    safe_print(f"⚠️  YAML syntax error on attempt {attempt + 1}: {e}")
                    if attempt < max_retries - 1:
                        continue
                    raise
                
                safe_print("📊 Validating enhanced requirements...")
                validation = self.validate_enhanced_requirements(yaml_content)
                
                if validation.get("passed", False):
                    safe_print("✅ All enhanced requirements met!")
                    break
                else:
                    safe_print(f"⚠️  Requirements not met on attempt {attempt + 1}:")
                    for issue in validation.get("issues", []):
                        safe_print(f"    - {issue}")
                    
                    if attempt < max_retries - 1:
                        safe_print("🔄 Retrying with more specific requirements...")
                        continue
                    else:
                        safe_print("⚠️  Proceeding with best attempt...")
                
            except Exception as e:
                safe_print(f"❌ Error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    continue
                raise
        
        # Save the configuration
        file_path = self.save_enhanced_yaml(yaml_content, domain, validation)
        
        return {
            "domain": domain,
            "file_path": file_path,
            "citations": citations,
            "yaml_content": yaml_content,
            "validation": validation,
            "enhanced": True
        }

def main():
    """Enhanced main function with comprehensive reporting."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced YAML Configuration Generator")
    parser.add_argument("--domain", required=True, help="Domain for use case generation")
    parser.add_argument("--instructions", default="data_generator_utils/instructions_for_usecase_data_creation.md", 
                       help="Instructions file path")
    parser.add_argument("--output-dir", default="data_generation/usecase_config_files", help="Output directory")
    
    args = parser.parse_args()
    
    try:
        generator = EnhancedUseCaseGenerator()
        
        result = generator.generate_enhanced_use_case(
            domain=args.domain,
            instructions_file=args.instructions
        )
        
        safe_print(f"🎉 ENHANCED CONFIGURATION GENERATED!")
        safe_print("=" * 60)
        safe_print(f"📁 File: {result['file_path']}")
        safe_print(f"🏷️  Domain: {result['domain']}")

        # Parse config to show display name
        try:
            config = yaml.safe_load(result['yaml_content'])
            display_name = config.get('display_name', 'Not specified')
            safe_print(f"📋 Display Name: {display_name}")
        except:
            pass    
        
        validation = result['validation']
        safe_print(f"\n📊 QUALITY METRICS:")
        safe_print(f"  ✅ Total Attributes: {validation.get('total_attributes', 0)}")
        safe_print(f"  ✅ Entities: {validation.get('entities_count', 0)}")
        safe_print(f"  ✅ Primary Entity Attributes: {validation.get('primary_entity_attributes', 0)}")
        safe_print(f"  ✅ High-Cardinality Fields: {validation.get('high_cardinality_fields', 0)}")
        safe_print(f"  ✅ List Fields: {validation.get('list_fields', 0)}")
        safe_print(f"  ✅ Temporal Fields: {validation.get('temporal_fields', 0)}")
        safe_print(f"  ✅ Template Placeholders: {validation.get('template_placeholders', 0)}")
        
        if validation.get('passed', False):
            safe_print(f"\n🏆 ALL ENHANCED REQUIREMENTS MET!")
        else:
            safe_print(f"\n⚠️  Some requirements not fully met:")
            for issue in validation.get('issues', []):
                safe_print(f"    - {issue}")
        
        if result['citations']:
            safe_print(f"\n📚 Research Sources ({len(result['citations'])}):") 
            for i, citation in enumerate(result['citations'][:5], 1):
                safe_print(f"  [{i}] {citation[:100]}...")
        
        safe_print(f"\n🚀 NEXT STEPS:")
        safe_print("1. Review: " + result['file_path'])
        safe_print("2. Test: python refined_generator.py --config " + result['file_path'] + " --preview")
        safe_print("3. Generate: python refined_generator.py --config " + result['file_path'] + " --num-examples 100")
        
        return 0
        
    except Exception as e:
        safe_print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
