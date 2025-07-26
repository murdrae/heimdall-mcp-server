#!/usr/bin/env python3
"""
Start Enhanced Heimdall System

This script initializes and starts the enhanced Heimdall architecture with
real Qdrant vector storage and optional migration from legacy data.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cognitive_memory.core.enhanced_memory import (
    EnhancedCognitiveMemory,
    TemporalWindow,
    MemoryDomain
)
from cognitive_memory.storage.enhanced_storage import EnhancedQdrantStorage
from cognitive_memory.retrieval.enhanced_query_engine import EnhancedQueryEngine
from cognitive_memory.retrieval.temporal_semantic_coordinator import TemporalSemanticCoordinator
from cognitive_memory.migration.enhanced_migration_tools import (
    LegacyHeimdallBridge,
    EnhancedMigrationEngine,
    MigrationOrchestrator
)


class EnhancedHeimdallSystem:
    """Complete enhanced Heimdall system manager."""
    
    def __init__(
        self,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        collection_prefix: str = "enhanced_heimdall",
        enable_migration: bool = True
    ):
        """Initialize the enhanced system."""
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.collection_prefix = collection_prefix
        self.enable_migration = enable_migration
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('enhanced_heimdall')
        
        # Initialize components
        self.storage = None
        self.query_engine = None
        self.coordinator = None
        self.migration_engine = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize all system components."""
        try:
            self.logger.info("🚀 Starting Enhanced Heimdall System...")
            
            # Initialize storage
            self.logger.info("📦 Initializing enhanced storage...")
            self.storage = EnhancedQdrantStorage(
                host=self.qdrant_host,
                port=self.qdrant_port,
                collection_prefix=self.collection_prefix
            )
            await self.storage.initialize()
            self.logger.info("✓ Enhanced storage initialized")
            
            # Initialize query engine
            self.logger.info("🔍 Initializing enhanced query engine...")
            self.query_engine = EnhancedQueryEngine()
            self.logger.info("✓ Enhanced query engine initialized")
            
            # Initialize coordinator
            self.logger.info("🎯 Initializing temporal-semantic coordinator...")
            self.coordinator = TemporalSemanticCoordinator(
                storage=self.storage,
                query_engine=self.query_engine,
                logger=self.logger
            )
            self.logger.info("✓ Temporal-semantic coordinator initialized")
            
            # Initialize migration engine if enabled
            if self.enable_migration:
                self.logger.info("🔄 Initializing migration engine...")
                self.migration_engine = EnhancedMigrationEngine(
                    enhanced_storage=self.storage,
                    logger=self.logger
                )
                self.logger.info("✓ Migration engine initialized")
            
            self.initialized = True
            self.logger.info("🎉 Enhanced Heimdall System ready!")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize enhanced system: {e}")
            raise
    
    async def store_memory(
        self,
        content: str,
        temporal_window: str = "active",
        semantic_domain: str = "ai_interactions",
        importance_score: float = 0.5,
        tags: list = None
    ) -> str:
        """Store a memory in the enhanced system."""
        if not self.initialized:
            await self.initialize()
        
        # Parse enums
        try:
            temporal_window_enum = TemporalWindow(temporal_window.lower())
        except ValueError:
            temporal_window_enum = TemporalWindow.ACTIVE
        
        try:
            semantic_domain_enum = MemoryDomain(semantic_domain.lower())
        except ValueError:
            semantic_domain_enum = MemoryDomain.AI_INTERACTIONS
        
        # Create memory
        memory = EnhancedCognitiveMemory(
            content=content,
            temporal_window=temporal_window_enum,
            semantic_domain=semantic_domain_enum,
            importance_score=importance_score
        )
        
        if tags:
            memory.user_defined_tags = set(tags)
        
        # Store memory
        self.storage.store_memory(memory)
        self.logger.info(f"✓ Stored memory: {memory.id[:8]}... in {temporal_window} window")
        
        return memory.id
    
    async def query_memories(
        self,
        query_text: str,
        query_type: str = "general_search",
        max_results: int = 10,
        temporal_focus: str = None,
        domain_focus: str = None
    ):
        """Query memories using the enhanced system."""
        if not self.initialized:
            await self.initialize()
        
        # Parse optional filters
        temporal_focus_enum = None
        if temporal_focus:
            try:
                temporal_focus_enum = TemporalWindow(temporal_focus.lower())
            except ValueError:
                pass
        
        domain_focus_enum = None
        if domain_focus:
            try:
                domain_focus_enum = MemoryDomain(domain_focus.lower())
            except ValueError:
                pass
        
        # Execute query
        results, metrics = await self.coordinator.query_memories(
            query_text=query_text,
            query_type=query_type,
            max_results=max_results,
            temporal_focus=temporal_focus_enum,
            domain_focus=domain_focus_enum
        )
        
        self.logger.info(
            f"🔍 Query '{query_text}' returned {len(results)} results in "
            f"{metrics.total_query_time:.3f}s"
        )
        
        return results, metrics
    
    async def get_system_status(self):
        """Get comprehensive system status."""
        if not self.initialized:
            await self.initialize()
        
        # Get storage statistics
        storage_stats = await self.storage.get_system_statistics()
        
        # Get performance statistics
        performance_stats = self.coordinator.get_performance_summary()
        
        return {
            'system_initialized': self.initialized,
            'timestamp': datetime.now().isoformat(),
            'storage_stats': storage_stats,
            'performance_stats': performance_stats,
            'configuration': {
                'qdrant_host': self.qdrant_host,
                'qdrant_port': self.qdrant_port,
                'collection_prefix': self.collection_prefix,
                'migration_enabled': self.enable_migration
            }
        }
    
    async def migrate_legacy_data(self, dry_run: bool = True):
        """Migrate data from legacy Heimdall system."""
        if not self.initialized:
            await self.initialize()
        
        if not self.enable_migration:
            raise RuntimeError("Migration is not enabled for this system")
        
        self.logger.info(f"🔄 Starting legacy data migration {'(DRY RUN)' if dry_run else ''}...")
        
        # Create legacy bridge
        legacy_bridge = LegacyHeimdallBridge(
            legacy_qdrant_host=self.qdrant_host,
            legacy_qdrant_port=self.qdrant_port,
            logger=self.logger
        )
        
        # Create orchestrator
        orchestrator = MigrationOrchestrator(
            legacy_bridge=legacy_bridge,
            migration_engine=self.migration_engine,
            logger=self.logger
        )
        
        # Run migration
        report = await orchestrator.run_full_migration(
            dry_run=dry_run,
            backup_legacy_data=not dry_run
        )
        
        return report


async def interactive_demo():
    """Run an interactive demo of the enhanced system."""
    print("🎯 Enhanced Heimdall Interactive Demo")
    print("=" * 50)
    
    # Initialize system
    system = EnhancedHeimdallSystem()
    await system.initialize()
    
    # Show system status
    print("\n📊 System Status:")
    status = await system.get_system_status()
    print(f"  ✓ Storage: {status['storage_stats']['total_memories']} memories")
    print(f"  ✓ Performance: {status['performance_stats'].get('total_queries', 0)} queries executed")
    
    # Store some demo memories
    print("\n📝 Storing demo memories...")
    
    demo_memories = [
        {
            "content": "Enhanced Heimdall system successfully started with real Qdrant storage",
            "temporal_window": "active",
            "semantic_domain": "session_continuity",
            "importance_score": 0.9,
            "tags": ["system_start", "enhanced", "demo"]
        },
        {
            "content": "Sierra Chart trading system development patterns and best practices for custom studies",
            "temporal_window": "reference",
            "semantic_domain": "technical_patterns",
            "importance_score": 0.8,
            "tags": ["sierra_chart", "patterns", "development"]
        },
        {
            "content": "NQ session pattern analysis project completion with 65.2% win rate results",
            "temporal_window": "working",
            "semantic_domain": "project_context",
            "importance_score": 0.95,
            "tags": ["nq_patterns", "trading", "analysis"]
        }
    ]
    
    memory_ids = []
    for memory_data in demo_memories:
        memory_id = await system.store_memory(**memory_data)
        memory_ids.append(memory_id)
        print(f"  ✓ Stored: {memory_data['content'][:50]}...")
    
    # Test queries
    print("\n🔍 Testing enhanced queries...")
    
    test_queries = [
        ("Sierra Chart patterns", "technical_pattern"),
        ("project status NQ", "project_status"),
        ("system startup", "session_continuity"),
        ("trading analysis", "general_search")
    ]
    
    for query_text, query_type in test_queries:
        results, metrics = await system.query_memories(
            query_text=query_text,
            query_type=query_type,
            max_results=3
        )
        
        print(f"  🔎 '{query_text}' ({query_type}): {len(results)} results in {metrics.total_query_time:.3f}s")
        for i, result in enumerate(results[:2]):  # Show top 2
            print(f"    {i+1}. [{result.memory.temporal_window.value.upper()}] "
                  f"Relevance: {result.relevance.total_score:.3f}")
            print(f"       {result.memory.content[:60]}...")
    
    # Show final status
    print("\n📈 Final System Status:")
    final_status = await system.get_system_status()
    print(f"  • Total Memories: {final_status['storage_stats']['total_memories']}")
    print(f"  • Active: {final_status['storage_stats']['active_memories']}")
    print(f"  • Working: {final_status['storage_stats']['working_memories']}")
    print(f"  • Reference: {final_status['storage_stats']['reference_memories']}")
    print(f"  • Archive: {final_status['storage_stats']['archive_memories']}")
    print(f"  • Queries Executed: {final_status['performance_stats']['total_queries']}")
    
    print("\n🎉 Enhanced Heimdall system is running successfully!")
    print("🔗 Ready for MCP integration with Claude Code")
    
    return system


async def main():
    """Main execution."""
    try:
        # Run interactive demo
        system = await interactive_demo()
        
        # Optional: Test migration (dry run)
        if system.enable_migration:
            print("\n🔄 Testing migration from legacy data...")
            try:
                migration_report = await system.migrate_legacy_data(dry_run=True)
                print(f"  📋 Migration analysis: {migration_report.successfully_migrated} memories ready to migrate")
            except Exception as e:
                print(f"  ⚠️  Migration test skipped: {e}")
        
        print("\n✅ Enhanced Heimdall is ready for production use!")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to start enhanced system: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)