#!/usr/bin/env python3
"""Tests for the database schema system."""

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent
import yaml

from app.database.schema import (
    SchemaParser, ModelGenerator, DatabaseSchema, TableDefinition, 
    ColumnDefinition, IndexDefinition, ConstraintDefinition, ColumnType,
    load_schema, generate_models_from_schema, generate_models_file
)


class TestSchemaParser(unittest.TestCase):
    """Test cases for SchemaParser."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.parser = SchemaParser()
        self.test_schema_data = {
            'database': 'test_db',
            'version': '1.0',
            'description': 'Test database',
            'tables': {
                'users': {
                    'description': 'User table',
                    'columns': [
                        {
                            'name': 'id',
                            'type': 'integer',
                            'primary_key': True,
                            'autoincrement': True
                        },
                        {
                            'name': 'username',
                            'type': 'text',
                            'length': 50,
                            'nullable': False,
                            'unique': True
                        },
                        {
                            'name': 'email',
                            'type': 'text',
                            'length': 255,
                            'nullable': False
                        },
                        {
                            'name': 'created_at',
                            'type': 'datetime',
                            'default': 'CURRENT_TIMESTAMP'
                        }
                    ],
                    'indexes': [
                        {
                            'name': 'idx_users_username',
                            'columns': ['username'],
                            'unique': True
                        }
                    ],
                    'constraints': [
                        {
                            'name': 'uq_users_email',
                            'type': 'unique',
                            'columns': ['email']
                        }
                    ]
                }
            }
        }
    
    def test_parse_dict_basic(self):
        """Test parsing basic schema dictionary."""
        schema = self.parser.parse_dict(self.test_schema_data)
        
        self.assertIsInstance(schema, DatabaseSchema)
        self.assertEqual(schema.database, 'test_db')
        self.assertEqual(schema.version, '1.0')
        self.assertEqual(schema.description, 'Test database')
        self.assertEqual(len(schema.tables), 1)
        self.assertIn('users', schema.tables)
    
    def test_parse_table(self):
        """Test parsing table definition."""
        table_data = self.test_schema_data['tables']['users']
        table = self.parser._parse_table('users', table_data)
        
        self.assertIsInstance(table, TableDefinition)
        self.assertEqual(table.name, 'users')
        self.assertEqual(table.description, 'User table')
        self.assertEqual(len(table.columns), 4)
        self.assertEqual(len(table.indexes), 1)
        self.assertEqual(len(table.constraints), 1)
    
    def test_parse_column(self):
        """Test parsing column definitions."""
        col_data = {
            'name': 'username',
            'type': 'text',
            'length': 50,
            'nullable': False,
            'unique': True,
            'note': 'User login name'
        }
        
        col = self.parser._parse_column(col_data)
        
        self.assertIsInstance(col, ColumnDefinition)
        self.assertEqual(col.name, 'username')
        self.assertEqual(col.type, ColumnType.TEXT)
        self.assertEqual(col.length, 50)
        self.assertFalse(col.nullable)
        self.assertTrue(col.unique)
        self.assertEqual(col.note, 'User login name')
    
    def test_parse_column_with_foreign_key(self):
        """Test parsing column with foreign key."""
        col_data = {
            'name': 'user_id',
            'type': 'integer',
            'nullable': False,
            'foreign_key': 'users.id'
        }
        
        col = self.parser._parse_column(col_data)
        
        self.assertEqual(col.foreign_key, 'users.id')
    
    def test_parse_index(self):
        """Test parsing index definition."""
        idx_data = {
            'name': 'idx_users_email',
            'columns': ['email', 'created_at'],
            'unique': False
        }
        
        idx = self.parser._parse_index(idx_data)
        
        self.assertIsInstance(idx, IndexDefinition)
        self.assertEqual(idx.name, 'idx_users_email')
        self.assertEqual(idx.columns, ['email', 'created_at'])
        self.assertFalse(idx.unique)
    
    def test_parse_constraint(self):
        """Test parsing constraint definition."""
        const_data = {
            'name': 'uq_users_email',
            'type': 'unique',
            'columns': ['email']
        }
        
        const = self.parser._parse_constraint(const_data)
        
        self.assertIsInstance(const, ConstraintDefinition)
        self.assertEqual(const.name, 'uq_users_email')
        self.assertEqual(const.type, 'unique')
        self.assertEqual(const.columns, ['email'])
    
    def test_parse_file(self):
        """Test parsing YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(self.test_schema_data, f)
            temp_path = Path(f.name)
        
        try:
            schema = self.parser.parse_file(temp_path)
            self.assertEqual(schema.database, 'test_db')
            self.assertEqual(len(schema.tables), 1)
        finally:
            temp_path.unlink()
    
    def test_invalid_column_type(self):
        """Test error handling for invalid column type."""
        col_data = {
            'name': 'test_col',
            'type': 'invalid_type'
        }
        
        with self.assertRaises(ValueError):
            self.parser._parse_column(col_data)
    
    def test_missing_file(self):
        """Test error handling for missing file."""
        with self.assertRaises(FileNotFoundError):
            self.parser.parse_file(Path('nonexistent.yml'))


class TestModelGenerator(unittest.TestCase):
    """Test cases for ModelGenerator."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.generator = ModelGenerator()
        self.parser = SchemaParser()
        
        # Simple test schema
        self.schema_data = {
            'database': 'test_db',
            'version': '1.0',
            'tables': {
                'simple_table': {
                    'description': 'Simple test table',
                    'columns': [
                        {
                            'name': 'id',
                            'type': 'integer',
                            'primary_key': True,
                            'autoincrement': True
                        },
                        {
                            'name': 'name',
                            'type': 'text',
                            'length': 100,
                            'nullable': False
                        },
                        {
                            'name': 'score',
                            'type': 'integer',
                            'default': 0
                        },
                        {
                            'name': 'created_at',
                            'type': 'datetime',
                            'default': 'CURRENT_TIMESTAMP'
                        }
                    ],
                    'indexes': [
                        {
                            'name': 'idx_simple_name',
                            'columns': ['name'],
                            'unique': True
                        }
                    ]
                }
            }
        }
        self.schema = self.parser.parse_dict(self.schema_data)
    
    def test_generate_models(self):
        """Test generating SQLAlchemy models."""
        models = self.generator.generate_models(self.schema)
        
        self.assertEqual(len(models), 1)
        self.assertIn('simple_table', models)
        
        SimpleTable = models['simple_table']
        
        # Check class name
        self.assertEqual(SimpleTable.__name__, 'SimpleTable')
        self.assertEqual(SimpleTable.__tablename__, 'simple_table')
        
        # Check columns exist
        self.assertTrue(hasattr(SimpleTable, 'id'))
        self.assertTrue(hasattr(SimpleTable, 'name'))
        self.assertTrue(hasattr(SimpleTable, 'score'))
        self.assertTrue(hasattr(SimpleTable, 'created_at'))
    
    def test_create_column_types(self):
        """Test column type mapping."""
        # Integer column
        col_def = ColumnDefinition('test_id', ColumnType.INTEGER, primary_key=True)
        col = self.generator._create_column(col_def)
        self.assertTrue(col.primary_key)
        
        # Text column with length
        col_def = ColumnDefinition('test_name', ColumnType.TEXT, length=50, nullable=False)
        col = self.generator._create_column(col_def)
        self.assertFalse(col.nullable)
        
        # Column with foreign key
        col_def = ColumnDefinition('user_id', ColumnType.INTEGER, foreign_key='users.id')
        col = self.generator._create_column(col_def)
        self.assertIsNotNone(col.foreign_keys)
    
    def test_generate_model_file(self):
        """Test generating Python model file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            temp_path = Path(f.name)
        
        try:
            self.generator.generate_model_file(self.schema, temp_path)
            
            # Check file was created and contains expected content
            self.assertTrue(temp_path.exists())
            content = temp_path.read_text()
            
            # Check for expected imports
            self.assertIn('from sqlalchemy import', content)
            self.assertIn('Base = declarative_base()', content)
            
            # Check for model class
            self.assertIn('class SimpleTable(Base):', content)
            self.assertIn('__tablename__ = "simple_table"', content)
            
            # Check for columns
            self.assertIn('id = Column(', content)
            self.assertIn('name = Column(', content)
            
        finally:
            temp_path.unlink()


class TestHighLevelFunctions(unittest.TestCase):
    """Test cases for high-level utility functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.schema_yaml = dedent("""
            database: example_database
            version: 1.0
            description: Example database for testing
            
            tables:
              example_table:
                description: Example table storing records
                columns:
                  - name: id
                    type: integer
                    primary_key: true
                    autoincrement: true
                  - name: name
                    type: text
                    nullable: false
                    length: 255
                  - name: count
                    type: integer
                    default: 0
                  - name: created_at
                    type: datetime
                    default: CURRENT_TIMESTAMP
                indexes:
                  - name: idx_example_name
                    columns: [name]
                    unique: true
        """).strip()
    
    def test_load_schema(self):
        """Test load_schema function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(self.schema_yaml)
            temp_path = Path(f.name)
        
        try:
            schema = load_schema(temp_path)
            self.assertEqual(schema.database, 'example_database')
            self.assertEqual(schema.version, '1.0')
            self.assertIn('example_table', schema.tables)
        finally:
            temp_path.unlink()
    
    def test_generate_models_from_schema(self):
        """Test generate_models_from_schema function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(self.schema_yaml)
            temp_path = Path(f.name)
        
        try:
            models = generate_models_from_schema(temp_path)
            self.assertEqual(len(models), 1)
            self.assertIn('example_table', models)
            
            ExampleTable = models['example_table']
            self.assertEqual(ExampleTable.__name__, 'ExampleTable')
        finally:
            temp_path.unlink()
    
    def test_generate_models_file(self):
        """Test generate_models_file function."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as schema_file:
            schema_file.write(self.schema_yaml)
            schema_path = Path(schema_file.name)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as output_file:
            output_path = Path(output_file.name)
        
        try:
            generate_models_file(schema_path, output_path)
            
            # Check output file was created
            self.assertTrue(output_path.exists())
            content = output_path.read_text()
            
            # Check for expected content
            self.assertIn('class ExampleTable(Base):', content)
            self.assertIn('__tablename__ = "example_table"', content)
            
        finally:
            schema_path.unlink()
            output_path.unlink()


def run_tests():
    """Run all tests."""
    print("🧪 Running Database Schema System Tests")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSchemaParser))
    suite.addTests(loader.loadTestsFromTestCase(TestModelGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestHighLevelFunctions))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n📊 Test Results:")
    print(f"   Tests run: {result.testsRun}")
    print(f"   Failures: {len(result.failures)}")
    print(f"   Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ Failures:")
        for test, traceback in result.failures:
            print(f"   - {test}: {traceback}")
    
    if result.errors:
        print(f"\n💥 Errors:")
        for test, traceback in result.errors:
            print(f"   - {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    if success:
        print(f"\n✅ All tests passed!")
    else:
        print(f"\n❌ Some tests failed.")
    
    return success


if __name__ == '__main__':
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)