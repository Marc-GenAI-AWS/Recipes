You are tasked with creating a comprehensive YAML configuration file for synthetic data generation. This file should generate highly diverse, realistic training data for fine-tuning large language models. Follow these detailed instructions to create configurations with maximum variety and depth:

Step 1: Deep Domain Research & Data Model Discovery

Multi-Source Research Strategy:

Industry Standards: Search for HL7, FHIR, ISO standards, industry data dictionaries

Real-World APIs: Examine Stripe, Salesforce, Epic, SAP API documentation for field structures

Open Datasets: Study Kaggle, government open data, academic datasets in your domain

Regulatory Requirements: Research GDPR, HIPAA, SOX compliance data requirements

Enterprise Software Schemas: Look at popular SaaS platforms' data models (HubSpot, Workday, etc.)

Identify Data Complexity Patterns:

Multi-level hierarchies (departments → teams → individuals)

Temporal data patterns (historical trends, seasonal variations)

Geographic variations (regional differences, localization needs)

Workflow states and transitions

Audit trails and versioning

Step 2: Entity Design for Maximum Variety

Create 4-6 Entities (not just 2-3):

1 Primary Entity: The main business object

2-3 Core Supporting Entities: Direct relationships

1-2 Reference/Lookup Entities: Categories, types, classifications

1 Historical/Audit Entity: Tracking changes over time

Attribute Richness Guidelines:

Primary Entity: 15-25 attributes minimum

Supporting Entities: 8-15 attributes each

Reference Entities: 5-10 attributes each

Step 3: Advanced Field Type Strategies

High-Cardinality Categorical Fields:
Instead of 3-5 categories, use 8-15+

industry:
type: categorical
categories: [Technology, Healthcare, Finance, Manufacturing, Retail, Education, Government, Non-profit, Energy, Transportation, Real Estate, Media, Telecommunications, Agriculture, Construction]

Multi-level categorizations:
product_category:
type: categorical
categories: [Electronics-Smartphones, Electronics-Laptops, Electronics-Tablets, Clothing-Mens, Clothing-Womens, Clothing-Kids, Home-Kitchen, Home-Furniture, Sports-Outdoor, Sports-Fitness]

Complex List Fields:
Multiple list types with varying lengths

skills:
type: list
min_length: 2
max_length: 12
description: Professional skills and competencies

certifications:
type: list
min_length: 0
max_length: 8
description: Professional certifications held

languages_spoken:
type: list
min_length: 1
max_length: 6
description: Languages with proficiency levels

Nested/Complex Attributes:
Geographic complexity:
location:
type: categorical
categories: [US-CA-San Francisco, US-NY-New York, US-TX-Austin, UK-London, DE-Berlin, JP-Tokyo, AU-Sydney, CA-Toronto, FR-Paris, SG-Singapore, IN-Bangalore, BR-São Paulo]

Time-based variations:
availability:
type: categorical
categories: [Full-time, Part-time, Contract, Seasonal, Weekend-only, Evening-shift, Night-shift, Remote, Hybrid, On-site]

Step 4: Demographic and Cultural Richness

Expand Cultural Dimensions:
cultural_background:
type: categorical
categories: [Hispanic-Mexican, Hispanic-Puerto Rican, Asian-Chinese, Asian-Indian, Asian-Filipino, Asian-Vietnamese, Asian-Korean, African-Nigerian, African-Ethiopian, European-German, European-Italian, Middle Eastern-Lebanese, South Asian-Pakistani, Pacific Islander-Hawaiian, Indigenous-Cherokee, Caribbean-Jamaican, Mixed-Heritage]

socioeconomic_status:
type: categorical
categories: [Lower-income, Lower-middle, Middle-class, Upper-middle, High-income, Ultra-high-net-worth]

education_level:
type: categorical
categories: [High School, Some College, Associates, Bachelors, Masters, PhD, Professional Degree, Trade Certification, Self-taught, International Equivalent]

Step 5: Temporal and Lifecycle Complexity

Multiple Date/Time Fields:
created_date:
type: datetime
min: "2020-01-01"
max: "2024-12-31"

last_updated:
type: datetime
min: "2024-01-01"
max: "now"

next_review_date:
type: datetime
min: "now"
max: "2026-12-31"

Seasonal patterns:
seasonal_activity:
type: categorical
categories: [Spring-High, Summer-Peak, Fall-Moderate, Winter-Low, Year-round-Stable, Holiday-Focused, Academic-Calendar, Fiscal-Year-End]

Step 6: Business Logic and Workflow States

Complex Status Hierarchies:
status:
type: categorical
categories: [Draft, Submitted, Under-Review, Pending-Approval, Approved, In-Progress, On-Hold, Escalated, Completed, Archived, Cancelled, Rejected, Requires-Revision]

priority_level:
type: categorical
categories: [Critical-P0, High-P1, Medium-P2, Low-P3, Deferred-P4, Nice-to-Have-P5]

risk_assessment:
type: categorical
categories: [Very-Low, Low, Medium-Low, Medium, Medium-High, High, Very-High, Critical]

Step 7: Quantitative Richness

Multiple Numeric Scales:
Different measurement scales:
satisfaction_score:
type: integer
min: 1
max: 10

nps_score:
type: integer
min: -100
max: 100

revenue:
type: integer
min: 10000
max: 50000000

employee_count:
type: integer
min: 1
max: 500000

Percentage fields:
completion_rate:
type: float
min: 0.0
max: 1.0

growth_rate:
type: float
min: -0.5
max: 3.0

Step 8: Enhanced Relationship Modeling

Multiple Relationship Types:
relationships:

from: Customer
to: Account
type: one-to-many
description: Customers can have multiple accounts

from: Account
to: Transaction
type: one-to-many
description: Accounts have transaction history

from: Customer
to: SupportTicket
type: one-to-many
description: Customer support interactions

from: Employee
to: Customer
type: many-to-many
description: Account management relationships

from: Product
to: Transaction
type: many-to-many
description: Products purchased in transactions

Step 9: Required YAML Structure

Your YAML file must follow this exact structure:

domain_name: [snake_case_domain_name]
display_name: "[Human-readable display name for web UI]"
description: [Brief description of the use case]

entities:

name: [EntityName]
description: [Entity description]
attributes:

name: [field_name]
type: [field_type]
[additional_constraints]
description: [Field description]

relationships:

from: [SourceEntity]
to: [TargetEntity]
type: [relationship_type]
description: [Relationship description]

fine_tuning_task:
task_type: text_generation
system_prompt: "[Domain-specific system prompt]"
user_template: "[Template with {field_name} placeholders]"
primary_entity: [MainEntity]

output_format: llama_chat
metadata_fields: [list_of_key_fields]

output:
format: jsonl
directory: usecase_data/[domain_name]

Step 10: Advanced Template Design

Multi-Context User Templates:
user_template: |
Analyze and provide recommendations for:

CUSTOMER PROFILE:

{first_name} {last_name}, {age} years old, {gender}

Cultural Background: {cultural_background}

Education: {education_level}, Income Level: {socioeconomic_status}

Location: {location}, Languages: {languages_spoken}

BUSINESS CONTEXT:

Industry: {industry}, Company Size: {employee_count} employees

Revenue: ${revenue}, Growth Rate: {growth_rate}%

Current Status: {status}, Priority: {priority_level}

ENGAGEMENT HISTORY:

Satisfaction Score: {satisfaction_score}/10, NPS: {nps_score}

Last Interaction: {last_updated}

Completion Rate: {completion_rate}%, Risk Level: {risk_assessment}

REQUIREMENTS:

Skills Needed: {skills}

Certifications: {certifications}

Availability: {availability}

Provide detailed analysis and actionable recommendations considering all cultural, business, and personal factors.

Step 11: Field Types Reference

Available Field Types:

id: For unique identifiers

first_name, last_name, full_name: For person names

integer: With realistic min/max ranges

float: For decimal numbers

categorical: With 8-15+ realistic categories

list: With min_length/max_length for collections

datetime: With appropriate date ranges

text: With max_length for long-form content

email, phone, address: For contact information

boolean: For true/false fields

Step 12: Quality Validation Checklist

Ensure your configuration includes:

50+ total attributes across all entities

At least 5 categorical fields with 10+ categories each

3+ list fields with varying cardinalities

Multiple temporal fields with different date ranges

Geographic/cultural diversity in categorical options

Business workflow complexity in status fields

Multiple numeric scales and measurement types

Rich user template that uses 15+ field placeholders

Step 13: Research Depth Requirements

For each domain, research and incorporate:

Review open source common data models and schemas

Industry-specific terminology and jargon

Regulatory compliance requirements

Cultural sensitivity considerations

Regional variations in practices

Technology stack commonly used

Performance metrics and KPIs

Workflow stages and approval processes

Integration touchpoints with other systems

Step 14: System Prompt Guidelines

Create a domain-specific system prompt that:

Defines the AI's role as a domain expert

Specifies the expected output format and tone

Includes any domain-specific guidelines or constraints

Mentions cultural, regulatory, or industry considerations

Example System Prompts by Domain:

Healthcare: "You are a medical professional creating comprehensive care plans. Your responses must be medically accurate, culturally sensitive, and compliant with healthcare regulations."

Business: "You are a business analyst providing strategic recommendations. Your responses should be data-driven, actionable, and consider market dynamics."

Legal: "You are a legal expert drafting documents. Your responses must be precise, compliant with relevant jurisdictions, and professionally formatted."

Step 15: Critical Requirements Checklist

MANDATORY SECTIONS - Your YAML must include ALL of these:

domain_name (snake_case format)

display_name (human-readable for web UI)

description

entities (4-6 entities with rich attributes)

relationships (between entities)

fine_tuning_task (CRITICAL - this section is required)

task_type: text_generation

system_prompt (domain-specific)

user_template (with 15+ field placeholders)

primary_entity

output_format: llama_chat

metadata_fields

output section

The fine_tuning_task section is absolutely mandatory and must include a comprehensive user_template with multiple field placeholders using {field_name} syntax.

Final Deliverable Requirements

Provide a complete, valid YAML file that:

Follows the exact structure shown above

Contains 4-6 well-designed entities with rich attributes

Includes appropriate relationships between entities

Has a domain-expert system prompt

Contains a comprehensive user template that will generate high-quality training examples

Uses realistic constraints and categories based on your research

Demonstrates deep understanding of the domain through terminology and data modeling

Includes ALL mandatory sections, especially fine_tuning_task

Is ready to use with the synthetic data generation system

Remember: The goal is to create a configuration that will generate realistic, highly diverse synthetic data that accurately represents real-world complexity and can be used to fine-tune LLMs for sophisticated domain-specific tasks. The fine_tuning_task section is critical for the system to work properly.