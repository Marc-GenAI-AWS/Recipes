#!/usr/bin/env python3
"""
Advanced Synthetic Data Generator for Enhanced YAML Configurations
Fully utilizes rich, diverse configurations with 50+ attributes and high cardinality.
"""

import yaml
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
from faker import Faker
from faker.providers import automotive, company, internet, person, address, phone_number
import argparse
import time

# Initialize Faker with multiple locales for diversity
fake = Faker(['en_US', 'en_GB', 'es_ES', 'fr_FR', 'de_DE', 'ja_JP', 'zh_CN', 'hi_IN'])

@dataclass
class GenerationStats:
    """Track generation statistics."""
    total_records: int = 0
    entities_generated: Dict[str, int] = None
    generation_time: float = 0.0
    validation_errors: List[str] = None
    
    def __post_init__(self):
        if self.entities_generated is None:
            self.entities_generated = {}
        if self.validation_errors is None:
            self.validation_errors = []

class AdvancedFieldGenerator:
    """Advanced field generator that handles complex, high-cardinality fields."""
    
    def __init__(self):
        self.generated_ids = set()
        self.context_cache = {}
        
        # Enhanced automotive data
        self.automotive_data = {
            'makes': ['Toyota', 'Honda', 'Ford', 'Chevrolet', 'BMW', 'Mercedes-Benz', 'Audi', 'Lexus', 'Nissan', 'Hyundai', 'Kia', 'Subaru', 'Mazda', 'Volkswagen', 'Porsche', 'Tesla', 'Volvo', 'Jaguar', 'Land Rover', 'Infiniti'],
            'models_by_make': {
                'Toyota': ['Camry', 'Corolla', 'RAV4', 'Highlander', 'Prius', 'Tacoma', 'Tundra', 'Sienna', 'Avalon', 'C-HR'],
                'Honda': ['Civic', 'Accord', 'CR-V', 'Pilot', 'Odyssey', 'Ridgeline', 'HR-V', 'Passport', 'Insight', 'Fit'],
                'BMW': ['3 Series', '5 Series', '7 Series', 'X3', 'X5', 'X7', 'i3', 'i8', 'Z4', 'M3'],
                'Tesla': ['Model S', 'Model 3', 'Model X', 'Model Y', 'Cybertruck', 'Roadster']
            },
            'fuel_types': ['Gasoline', 'Diesel', 'Hybrid', 'Electric', 'Plug-in Hybrid', 'Hydrogen', 'CNG', 'LPG', 'Ethanol', 'Solar'],
            'drivetrains': ['FWD', 'RWD', 'AWD', '4WD', 'eAWD'],
            'body_styles': ['Sedan', 'SUV', 'Hatchback', 'Coupe', 'Convertible', 'Wagon', 'Pickup', 'Minivan', 'Crossover', 'Sports Car']
        }
        
        # Business context data
        self.business_data = {
            'company_sizes': ['Startup', 'Small', 'Medium', 'Large', 'Enterprise', 'Fortune 500'],
            'departments': ['Sales', 'Marketing', 'Engineering', 'HR', 'Finance', 'Operations', 'Customer Success', 'Product', 'Legal', 'IT'],
            'job_levels': ['Entry', 'Junior', 'Mid', 'Senior', 'Lead', 'Principal', 'Director', 'VP', 'C-Level'],
            'skills': ['Python', 'JavaScript', 'SQL', 'Project Management', 'Data Analysis', 'Machine Learning', 'Cloud Computing', 'DevOps', 'UI/UX Design', 'Sales Strategy', 'Digital Marketing', 'Financial Analysis']
        }
    
    def generate_unique_id(self, prefix: str = "") -> str:
        """Generate unique ID with optional prefix."""
        while True:
            new_id = f"{prefix}{uuid.uuid4().hex[:8]}" if prefix else str(uuid.uuid4())
            if new_id not in self.generated_ids:
                self.generated_ids.add(new_id)
                return new_id
    
    def generate_field_value(self, attribute: Dict[str, Any], context: Dict[str, Any] = None) -> Any:
        """Generate field value based on attribute configuration and context."""
        field_type = attribute['type']
        field_name = attribute.get('name', '').lower()
        
        # Context-aware generation
        if context is None:
            context = {}
        
        if field_type == 'id':
            return self.generate_unique_id()
        
        elif field_type == 'first_name':
            return fake.first_name()
        
        elif field_type == 'last_name':
            return fake.last_name()
        
        elif field_type == 'full_name':
            return fake.name()
        
        elif field_type == 'email':
            return fake.email()
        
        elif field_type == 'phone':
            return fake.phone_number()
        
        elif field_type == 'address':
            return fake.address().replace('\n', ', ')
        
        elif field_type == 'integer':
            min_val = attribute.get('min', 0)
            max_val = attribute.get('max', 100)
            
            # Context-aware integer generation
            if 'mileage' in field_name:
                return random.randint(0, 200000)
            elif 'year' in field_name:
                return random.randint(2015, 2025)
            elif 'price' in field_name or 'revenue' in field_name:
                return random.randint(min_val, max_val)
            else:
                return random.randint(min_val, max_val)
        
        elif field_type == 'float':
            min_val = attribute.get('min', 0.0)
            max_val = attribute.get('max', 1.0)
            return round(random.uniform(min_val, max_val), 2)
        
        elif field_type == 'boolean':
            return random.choice([True, False])
        
        elif field_type == 'categorical':
            categories = attribute.get('categories', [])
            if not categories:
                return None
            
            # Weighted selection for more realistic distributions
            if 'status' in field_name:
                # Generate weights that match the number of categories
                num_categories = len(categories)
                if num_categories == 1:
                    weights = [1.0]
                elif num_categories == 2:
                    weights = [0.7, 0.3]
                elif num_categories == 3:
                    weights = [0.5, 0.3, 0.2]
                elif num_categories == 4:
                    weights = [0.4, 0.3, 0.2, 0.1]
                elif num_categories == 5:
                    weights = [0.4, 0.3, 0.15, 0.1, 0.05]
                else:
                    # For more than 5 categories, create a decreasing weight distribution
                    weights = []
                    remaining_weight = 1.0
                    for i in range(num_categories):
                        if i == num_categories - 1:
                            # Last category gets remaining weight
                            weights.append(remaining_weight)
                        else:
                            # Each category gets progressively less weight
                            weight = remaining_weight * (0.5 ** i) * 0.6
                            weights.append(weight)
                            remaining_weight -= weight
                    
                    # Normalize weights to sum to 1.0
                    total_weight = sum(weights)
                    weights = [w / total_weight for w in weights]
                
                return random.choices(categories, weights=weights)[0]
            else:
                return random.choice(categories)
        
        elif field_type == 'list':
            min_length = attribute.get('min_length', 0)
            max_length = attribute.get('max_length', 5)
            length = random.randint(min_length, max_length)
            
            if length == 0:
                return []
            
            # Generate context-appropriate list items
            if 'skill' in field_name:
                available_items = self.business_data['skills']
            elif 'language' in field_name:
                available_items = ['English', 'Spanish', 'French', 'German', 'Chinese', 'Japanese', 'Arabic', 'Portuguese', 'Russian', 'Hindi', 'Italian', 'Korean']
            elif 'certification' in field_name:
                available_items = ['AWS Certified', 'Google Cloud Certified', 'Microsoft Certified', 'Salesforce Certified', 'PMP', 'Six Sigma', 'CISSP', 'CPA', 'MBA', 'PhD']
            elif 'condition' in field_name or 'medical' in field_name:
                available_items = ['Hypertension', 'Diabetes', 'Asthma', 'Arthritis', 'Depression', 'Anxiety', 'Migraine', 'Back Pain', 'High Cholesterol', 'Sleep Apnea']
            elif 'allerg' in field_name:
                available_items = ['Peanuts', 'Shellfish', 'Dairy', 'Eggs', 'Soy', 'Wheat', 'Tree Nuts', 'Fish', 'Sesame', 'Latex', 'Penicillin', 'Sulfa', 'Ibuprofen', 'Aspirin', 'Dust Mites', 'Pollen', 'Pet Dander', 'Mold']
            else:
                available_items = [fake.word() for _ in range(20)]
            
            # Ensure no duplicates
            selected_items = random.sample(available_items, min(length, len(available_items)))
            return selected_items
        
        elif field_type in ['datetime', 'date']:
            min_date = attribute.get('min', '2020-01-01')
            max_date = attribute.get('max', 'now')
            
            try:
                if min_date == 'now':
                    start_date = datetime.now()
                else:
                    start_date = datetime.strptime(min_date, '%Y-%m-%d')
                
                if max_date == 'now':
                    end_date = datetime.now()
                else:
                    end_date = datetime.strptime(max_date, '%Y-%m-%d')
                
                if start_date > end_date:
                    start_date, end_date = end_date, start_date
                
                # Generate random datetime between start and end
                time_between = end_date - start_date
                days_between = time_between.days
                random_days = random.randint(0, days_between)
                random_date = start_date + timedelta(days=random_days)
                
                if field_type == 'date':
                    return random_date.strftime('%Y-%m-%d')
                else:
                    # Add random time
                    random_time = timedelta(
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59),
                        seconds=random.randint(0, 59)
                    )
                    random_datetime = random_date + random_time
                    return random_datetime.strftime('%Y-%m-%d %H:%M:%S')
            
            except Exception:
                # Fallback to current date/time
                now = datetime.now()
                if field_type == 'date':
                    return now.strftime('%Y-%m-%d')
                else:
                    return now.strftime('%Y-%m-%d %H:%M:%S')
        
        elif field_type == 'text':
            max_length = attribute.get('max_length', 500)
            
            # Generate context-aware text
            if 'description' in field_name or 'summary' in field_name:
                return fake.text(max_nb_chars=max_length)
            elif 'note' in field_name or 'comment' in field_name:
                return fake.sentence(nb_words=random.randint(5, 20))
            elif 'rationale' in field_name or 'reason' in field_name:
                return self.generate_business_rationale(context, max_length)
            else:
                return fake.text(max_nb_chars=max_length)
        
        # Automotive-specific fields
        elif field_type == 'vin':
            return fake.vin()
        
        elif field_type == 'license_plate':
            return fake.license_plate()
        
        # Fallback
        else:
            return fake.word()
    
    def generate_business_rationale(self, context: Dict[str, Any], max_length: int) -> str:
        """Generate business rationale text based on context."""
        templates = [
            "Based on the analysis of {context_factor}, this recommendation aligns with industry best practices and addresses key business objectives.",
            "The proposed solution takes into account {context_factor} and provides optimal value while minimizing risk exposure.",
            "After evaluating multiple factors including {context_factor}, this approach offers the best balance of cost-effectiveness and performance.",
            "This recommendation is supported by {context_factor} and demonstrates strong potential for achieving desired outcomes.",
            "The strategic alignment with {context_factor} makes this the preferred option for long-term success."
        ]
        
        context_factors = [
            "market conditions", "customer requirements", "regulatory compliance", "budget constraints",
            "technical specifications", "competitive landscape", "risk assessment", "performance metrics",
            "stakeholder feedback", "industry trends", "operational efficiency", "scalability needs"
        ]
        
        template = random.choice(templates)
        factor = random.choice(context_factors)
        rationale = template.format(context_factor=factor)
        
        return rationale[:max_length]

class EnhancedDataGenerator:
    """Enhanced data generator that fully utilizes rich YAML configurations."""
    
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config = self.load_config()
        self.field_generator = AdvancedFieldGenerator()
        self.entity_data_cache = {}
        self.stats = GenerationStats()
        
        # Validate configuration
        self.validate_config()
    
    def load_config(self) -> Dict[str, Any]:
        """Load and parse YAML configuration."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            return config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")
    
    def validate_config(self):
        """Validate configuration structure."""
        required_sections = ['domain_name', 'entities', 'fine_tuning_task']
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        if not self.config.get('entities'):
            raise ValueError("No entities defined in configuration")
        
        # Count total attributes for validation
        total_attrs = sum(len(entity.get('attributes', [])) for entity in self.config['entities'])
        if total_attrs < 20:  # Minimum threshold
            print(f"WARNING: Only {total_attrs} total attributes found. Consider adding more for richer data.")
    
    def generate_entity_data(self, entity_config: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate data for a single entity with full attribute utilization."""
        entity_name = entity_config['name']
        attributes = entity_config.get('attributes', [])
        
        if not attributes:
            return {}
        
        entity_data = {}
        generation_context = context or {}
        
        # Generate all attributes
        for attribute in attributes:
            field_name = attribute['name']
            try:
                # Pass entity context to field generator
                field_context = {**generation_context, 'entity_name': entity_name}
                value = self.field_generator.generate_field_value(attribute, field_context)
                entity_data[field_name] = value
                
                # Update context with generated values for dependent fields
                generation_context[field_name] = value
                
            except Exception as e:
                print(f"ERROR generating field '{field_name}': {e}")
                entity_data[field_name] = None
        
        return entity_data
    
    def generate_related_entities(self, num_records: int) -> Dict[str, List[Dict[str, Any]]]:
        """Generate related entities maintaining referential integrity."""
        all_entity_data = {}
        
        # Generate entities in dependency order
        entities_by_name = {entity['name']: entity for entity in self.config['entities']}
        relationships = self.config.get('relationships', [])
        
        # Build dependency graph
        dependencies = {}
        for rel in relationships:
            from_entity = rel['from']
            to_entity = rel['to']
            if to_entity not in dependencies:
                dependencies[to_entity] = []
            dependencies[to_entity].append(from_entity)
        
        # Generate entities in order
        for entity_config in self.config['entities']:
            entity_name = entity_config['name']
            entity_records = []
            
            print(f"  Generating {entity_name} entities...")
            
            for i in range(num_records):
                # Create context from related entities
                context = {}
                
                # Add references to parent entities
                for rel in relationships:
                    if rel['to'] == entity_name and rel['from'] in all_entity_data:
                        parent_records = all_entity_data[rel['from']]
                        if parent_records:
                            # Reference a random parent record
                            parent_record = random.choice(parent_records)
                            # Add parent ID to context
                            parent_id_field = f"{rel['from'].lower()}_id"
                            if 'id' in parent_record:
                                context[parent_id_field] = parent_record['id']
                
                entity_data = self.generate_entity_data(entity_config, context)
                entity_records.append(entity_data)
            
            all_entity_data[entity_name] = entity_records
            self.stats.entities_generated[entity_name] = len(entity_records)
        
        return all_entity_data
    
    def create_training_example(self, entity_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Create a training example using the fine-tuning configuration."""
        ft_config = self.config.get('fine_tuning_task', {})
        system_prompt = ft_config.get('system_prompt', 'You are a helpful assistant.')
        user_template = ft_config.get('user_template', 'Generate content based on: {data}')
        
        # Flatten all entity data for template variables
        template_vars = {}
        
        # Select one record from each entity for this training example
        for entity_name, records in entity_data.items():
            if records:
                selected_record = random.choice(records)
                
                # Add all fields from selected record
                for key, value in selected_record.items():
                    template_vars[key] = value
                    # Also add with entity prefix
                    template_vars[f"{entity_name.lower()}_{key}"] = value
        
        # Format values for template
        formatted_vars = {}
        for key, value in template_vars.items():
            if isinstance(value, list):
                formatted_vars[key] = ', '.join(map(str, value)) if value else 'None'
            elif value is None:
                formatted_vars[key] = 'Not specified'
            else:
                formatted_vars[key] = str(value)
        
        # Generate user message
        try:
            user_message = user_template.format(**formatted_vars)
        except KeyError as e:
            # Handle missing template variables gracefully
            print(f"⚠️  Missing template variable {e}, using available data")
            # Use only available variables
            available_vars = {k: v for k, v in formatted_vars.items() if k in user_template}
            user_message = user_template.format(**available_vars) if available_vars else user_template
        
        # Generate assistant response
        assistant_response = self.generate_assistant_response(template_vars, ft_config)
        
        # Create training example
        training_example = {
            "dialog": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response}
            ]
        }
        
        # Add metadata if specified
        metadata_fields = self.config.get('metadata_fields', [])
        if metadata_fields:
            metadata = {}
            for field in metadata_fields:
                if field in template_vars:
                    metadata[field] = template_vars[field]
            if metadata:
                training_example['metadata'] = metadata
        
        return training_example
    
    def generate_assistant_response(self, context: Dict[str, Any], ft_config: Dict[str, Any]) -> str:
        """Generate contextually appropriate assistant response."""
        domain_name = self.config.get('domain_name', 'general')
        
        # Look for existing rationale or content in context
        for key, value in context.items():
            if 'rationale' in key.lower() and value:
                return str(value)
            elif 'content' in key.lower() and value and len(str(value)) > 50:
                return str(value)
        
        # Generate domain-specific response
        if 'automotive' in domain_name or 'sales' in domain_name:
            return self.generate_sales_response(context)
        elif 'healthcare' in domain_name or 'medical' in domain_name:
            return self.generate_healthcare_response(context)
        elif 'finance' in domain_name or 'banking' in domain_name:
            return self.generate_finance_response(context)
        else:
            return self.generate_generic_response(context)
    
    def generate_sales_response(self, context: Dict[str, Any]) -> str:
        """Generate sales-specific response."""
        templates = [
            "Based on the customer profile and requirements, I recommend focusing on {key_factor}. This approach will address their specific needs while maximizing value proposition.",
            "The analysis indicates strong potential for {outcome}. Key considerations include budget alignment, feature requirements, and timeline expectations.",
            "This opportunity presents excellent potential with the right approach. Priority should be given to {priority_area} to ensure successful closure.",
            "Given the customer's background and stated requirements, the optimal strategy involves {strategy_focus} while maintaining competitive positioning."
        ]
        
        factors = ['value proposition', 'competitive advantages', 'ROI demonstration', 'risk mitigation', 'implementation timeline']
        outcomes = ['successful deal closure', 'long-term partnership', 'expanded account penetration', 'referral opportunities']
        priorities = ['relationship building', 'technical validation', 'financial justification', 'stakeholder alignment']
        strategies = ['consultative selling', 'solution customization', 'phased implementation', 'pilot program initiation']
        
        template = random.choice(templates)
        response = template.format(
            key_factor=random.choice(factors),
            outcome=random.choice(outcomes),
            priority_area=random.choice(priorities),
            strategy_focus=random.choice(strategies)
        )
        
        return response
    
    def generate_healthcare_response(self, context: Dict[str, Any]) -> str:
        """Generate healthcare-specific response."""
        return "Based on the patient profile and medical history, I recommend a comprehensive care approach that addresses all identified conditions while considering cultural and personal preferences. Regular monitoring and follow-up will be essential for optimal outcomes."
    
    def generate_finance_response(self, context: Dict[str, Any]) -> str:
        """Generate finance-specific response."""
        return "The financial analysis indicates several key considerations for risk management and portfolio optimization. Diversification strategies and regulatory compliance should be prioritized in the implementation plan."
    
    def generate_generic_response(self, context: Dict[str, Any]) -> str:
        """Generate generic response."""
        return "Based on the provided information and analysis, I recommend a strategic approach that addresses the key requirements while optimizing for efficiency and effectiveness. Regular review and adjustment will ensure continued success."
    
    def generate_dataset(self, num_examples: int) -> List[Dict[str, Any]]:
        """Generate complete dataset with specified number of examples."""
        print(f"Generating {num_examples} training examples for {self.config['domain_name']}")
        
        start_time = time.time()
        dataset = []
        
        # Generate entity data once and reuse for multiple training examples
        print("Generating entity data...")
        entity_data = self.generate_related_entities(max(num_examples // 2, 10))  # Generate reasonable number of entities
        
        print("Creating training examples...")
        for i in range(num_examples):
            if (i + 1) % 50 == 0:
                print(f"  Generated {i + 1}/{num_examples} examples")
            
            try:
                training_example = self.create_training_example(entity_data)
                dataset.append(training_example)
            except Exception as e:
                print(f"WARNING: Error generating example {i + 1}: {e}")
                self.stats.validation_errors.append(f"Example {i + 1}: {str(e)}")
                continue
        
        self.stats.total_records = len(dataset)
        self.stats.generation_time = time.time() - start_time
        
        return dataset
    
    def save_dataset(self, dataset: List[Dict[str, Any]], output_path: str = None) -> str:
        """Save dataset to JSONL file with metadata."""
        if output_path is None:
            output_config = self.config.get('output', {})
            directory = output_config.get('directory', 'usecase_data')
            Path(directory).mkdir(parents=True, exist_ok=True)
            
            domain_name = self.config['domain_name']
            timestamp = int(time.time())
            output_path = f"{directory}/{domain_name}/{domain_name}_{timestamp}.jsonl"
        
        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Save dataset
        with open(output_path, 'w', encoding='utf-8') as f:
            for example in dataset:
                f.write(json.dumps(example, ensure_ascii=False) + '\n')
        
        # Save generation metadata
        metadata_path = output_path.replace('.jsonl', '_metadata.json')
        metadata = {
            'domain_name': self.config['domain_name'],
            'config_path': self.config_path,
            'generation_timestamp': datetime.now().isoformat(),
            'total_examples': len(dataset),
            'entities_generated': self.stats.entities_generated,
            'generation_time_seconds': self.stats.generation_time,
            'validation_errors': self.stats.validation_errors,
            'config_summary': {
                'total_entities': len(self.config['entities']),
                'total_attributes': sum(len(entity.get('attributes', [])) for entity in self.config['entities']),
                'relationships': len(self.config.get('relationships', [])),
                'metadata_fields': self.config.get('metadata_fields', [])
            }
        }
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        with open("config.yaml", "r") as file:
            config = yaml.safe_load(file)

        config['local_input_data_path'] = output_path

        with open("config.yaml", "w") as file:
            yaml.dump(config, file)
        
        return output_path

    def print_generation_summary(self, dataset: List[Dict[str, Any]], output_path: str):
        """Print comprehensive generation summary."""
        print(f"\nDATASET GENERATION COMPLETE!")
        print("=" * 60)
        print(f"Output File: {output_path}")
        print(f"Metadata File: {output_path.replace('.jsonl', '_metadata.json')}")
        print(f"Domain: {self.config['domain_name']}")
        print(f"Examples Generated: {len(dataset)}")
        print(f"Generation Time: {self.stats.generation_time:.2f} seconds")
        
        print(f"\nENTITY STATISTICS:")
        for entity_name, count in self.stats.entities_generated.items():
            print(f"  * {entity_name}: {count} records")
        
        config_summary = {
            'total_entities': len(self.config['entities']),
            'total_attributes': sum(len(entity.get('attributes', [])) for entity in self.config['entities']),
            'relationships': len(self.config.get('relationships', [])),
        }
        
        print(f"\nCONFIGURATION UTILIZATION:")
        print(f"  * Entities: {config_summary['total_entities']}")
        print(f"  * Total Attributes: {config_summary['total_attributes']}")
        print(f"  * Relationships: {config_summary['relationships']}")
        
        if self.stats.validation_errors:
            print(f"\nVALIDATION WARNINGS ({len(self.stats.validation_errors)}):")
            for error in self.stats.validation_errors[:5]:  # Show first 5
                print(f"  * {error}")
            if len(self.stats.validation_errors) > 5:
                print(f"  * ... and {len(self.stats.validation_errors) - 5} more")
        
        print(f"\nNEXT STEPS:")
        print(f"1. Review generated data: head -n 3 {output_path}")
        print(f"2. Validate format: python -c \"import json; [json.loads(line) for line in open('{output_path}')]\"")
        print(f"3. Start fine-tuning with your preferred framework")

def main():
    """Enhanced main function with comprehensive options."""
    parser = argparse.ArgumentParser(description="Advanced Synthetic Data Generator")
    parser.add_argument("--config", required=True, help="Path to YAML configuration file")
    parser.add_argument("--num-examples", type=int, default=100, help="Number of training examples to generate")
    parser.add_argument("--output", help="Output file path (optional)")
    parser.add_argument("--preview", action="store_true", help="Show preview of generated data")
    parser.add_argument("--validate-only", action="store_true", help="Only validate configuration")
    
    args = parser.parse_args()
    
    try:
        # Initialize generator
        generator = EnhancedDataGenerator(args.config)
        
        if args.validate_only:
            print("VALIDATION PASSED: Configuration is valid!")
            return 0
        
        if args.preview:
            print("PREVIEW MODE - Generating sample data...")
            entity_data = generator.generate_related_entities(2)
            example = generator.create_training_example(entity_data)
            print(json.dumps(example, indent=2, ensure_ascii=False))
            return 0
        
        # Generate full dataset
        dataset = generator.generate_dataset(args.num_examples)
        output_path = generator.save_dataset(dataset, args.output)
        generator.print_generation_summary(dataset, output_path)
        
        return 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    exit(main())