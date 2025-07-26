"""
Migration tools for transitioning from legacy Heimdall to enhanced architecture.

This module provides tools to migrate existing L0/L1/L2 hierarchy data to the
new temporal-semantic architecture while preserving all information and relationships.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import json
from pathlib import Path

from ..core.enhanced_memory import (
    EnhancedCognitiveMemory,
    TemporalWindow,
    MemoryDomain,
    SemanticCluster,
    MemoryRelationship
)
from ..storage.enhanced_storage import EnhancedQdrantStorage


@dataclass
class LegacyMemory:
    """Represents a memory from the legacy L0/L1/L2 system."""
    
    id: str
    content: str
    hierarchy_level: int  # 0, 1, or 2
    memory_type: str  # semantic, episodic
    strength: float
    created_date: datetime
    last_accessed: datetime
    access_count: int
    importance_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)


@dataclass
class MigrationReport:
    """Report on migration progress and results."""
    
    total_legacy_memories: int = 0
    successfully_migrated: int = 0
    failed_migrations: int = 0
    
    # Breakdown by legacy hierarchy
    l0_migrated: int = 0
    l1_migrated: int = 0
    l2_migrated: int = 0
    
    # Breakdown by new temporal windows
    active_memories: int = 0
    working_memories: int = 0
    reference_memories: int = 0
    archive_memories: int = 0
    
    # Migration issues
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Performance metrics
    migration_duration: float = 0.0
    memories_per_second: float = 0.0
    
    def add_error(self, error: str) -> None:
        """Add an error to the migration report."""
        self.errors.append(error)
        self.failed_migrations += 1
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the migration report."""
        self.warnings.append(warning)
    
    def finalize(self, duration: float) -> None:
        """Finalize the migration report with timing information."""
        self.migration_duration = duration
        if duration > 0:
            self.memories_per_second = self.successfully_migrated / duration


class LegacyHeimdallBridge:
    """
    Bridge to read data from legacy Heimdall instances.
    
    This class handles reading from the old L0/L1/L2 Qdrant collections
    and SQLite metadata to extract all existing memories.
    """
    
    def __init__(
        self,
        legacy_qdrant_host: str = "localhost",
        legacy_qdrant_port: int = 6333,
        collection_prefix: str = "heimdall",
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the legacy Heimdall bridge."""
        self.legacy_qdrant_host = legacy_qdrant_host
        self.legacy_qdrant_port = legacy_qdrant_port
        self.collection_prefix = collection_prefix
        self.logger = logger or logging.getLogger(__name__)
        
        # Legacy collection names
        self.legacy_collections = {
            0: f"{collection_prefix}_L0_concepts",
            1: f"{collection_prefix}_L1_contexts", 
            2: f"{collection_prefix}_L2_episodes"
        }
    
    async def extract_all_legacy_memories(self) -> List[LegacyMemory]:
        """Extract all memories from legacy Heimdall collections."""
        all_memories = []
        
        try:
            # Import Qdrant client (may not be available in all environments)
            from qdrant_client import QdrantClient
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            client = QdrantClient(
                host=self.legacy_qdrant_host,
                port=self.legacy_qdrant_port
            )
            
            # Extract from each legacy collection
            for level, collection_name in self.legacy_collections.items():
                try:
                    # Check if collection exists
                    collections = await client.get_collections()
                    collection_exists = any(
                        c.name == collection_name 
                        for c in collections.collections
                    )
                    
                    if not collection_exists:
                        self.logger.warning(f"Legacy collection {collection_name} not found")
                        continue
                    
                    # Get all points from collection
                    scroll_result = await client.scroll(
                        collection_name=collection_name,
                        limit=1000,  # Process in batches
                        with_payload=True,
                        with_vectors=False  # We'll extract vectors separately if needed
                    )
                    
                    # Convert to LegacyMemory objects
                    for point in scroll_result[0]:
                        legacy_memory = self._convert_point_to_legacy_memory(
                            point, level
                        )
                        if legacy_memory:
                            all_memories.append(legacy_memory)
                    
                    self.logger.info(
                        f"Extracted {len(scroll_result[0])} memories from {collection_name}"
                    )
                    
                except Exception as e:
                    self.logger.error(f"Failed to extract from {collection_name}: {e}")
                    continue
            
            self.logger.info(f"Total legacy memories extracted: {len(all_memories)}")
            return all_memories
            
        except ImportError:
            self.logger.error("Qdrant client not available for legacy extraction")
            return []
        except Exception as e:
            self.logger.error(f"Failed to extract legacy memories: {e}")
            return []
    
    def _convert_point_to_legacy_memory(
        self, 
        point: Any, 
        hierarchy_level: int
    ) -> Optional[LegacyMemory]:
        """Convert a Qdrant point to a LegacyMemory object."""
        try:
            payload = point.payload or {}
            
            # Extract required fields
            memory_id = str(point.id)
            content = payload.get('content', '')
            
            # Extract temporal information
            created_str = payload.get('created_date', '')
            accessed_str = payload.get('last_accessed', '')
            
            try:
                created_date = datetime.fromisoformat(created_str) if created_str else datetime.now()
                last_accessed = datetime.fromisoformat(accessed_str) if accessed_str else datetime.now()
            except ValueError:
                created_date = datetime.now()
                last_accessed = datetime.now()
            
            # Extract other metadata
            memory_type = payload.get('memory_type', 'semantic')
            strength = float(payload.get('strength', 1.0))
            access_count = int(payload.get('access_count', 0))
            importance_score = float(payload.get('importance_score', 0.0))
            
            # Extract tags
            tags = set(payload.get('tags', []))
            
            # Create legacy memory object
            return LegacyMemory(
                id=memory_id,
                content=content,
                hierarchy_level=hierarchy_level,
                memory_type=memory_type,
                strength=strength,
                created_date=created_date,
                last_accessed=last_accessed,
                access_count=access_count,
                importance_score=importance_score,
                metadata=payload,
                tags=tags
            )
            
        except Exception as e:
            self.logger.error(f"Failed to convert point {point.id}: {e}")
            return None


class EnhancedMigrationEngine:
    """
    Core migration engine for converting legacy memories to enhanced architecture.
    
    This engine implements intelligent mapping rules to convert L0/L1/L2 memories
    into the new temporal-semantic organization.
    """
    
    def __init__(
        self,
        enhanced_storage: EnhancedQdrantStorage,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the migration engine."""
        self.enhanced_storage = enhanced_storage
        self.logger = logger or logging.getLogger(__name__)
        
        # Mapping rules for hierarchy to temporal windows
        self.temporal_mapping_rules = {
            # L0 concepts usually become reference knowledge
            0: {
                'default_window': TemporalWindow.REFERENCE,
                'conditions': {
                    'recent_access': TemporalWindow.WORKING,  # Recently accessed L0 -> WORKING
                    'very_recent': TemporalWindow.ACTIVE      # Very recently accessed L0 -> ACTIVE
                }
            },
            # L1 contexts become working memory or reference
            1: {
                'default_window': TemporalWindow.WORKING,
                'conditions': {
                    'old_unused': TemporalWindow.ARCHIVE,     # Old unused L1 -> ARCHIVE
                    'very_recent': TemporalWindow.ACTIVE      # Very recent L1 -> ACTIVE
                }
            },
            # L2 episodes usually become active or archive
            2: {
                'default_window': TemporalWindow.ACTIVE,
                'conditions': {
                    'old': TemporalWindow.ARCHIVE,            # Old L2 -> ARCHIVE
                    'important': TemporalWindow.WORKING       # Important L2 -> WORKING
                }
            }
        }
        
        # Domain inference rules based on content patterns
        self.domain_inference_rules = [
            {
                'pattern': ['project', 'status', 'milestone', 'phase'],
                'domain': MemoryDomain.PROJECT_CONTEXT
            },
            {
                'pattern': ['architecture', 'pattern', 'implementation', 'code'],
                'domain': MemoryDomain.TECHNICAL_PATTERNS
            },
            {
                'pattern': ['decision', 'rationale', 'trade-off', 'chosen'],
                'domain': MemoryDomain.DECISION_CHAINS
            },
            {
                'pattern': ['session', 'handoff', 'next', 'blocker'],
                'domain': MemoryDomain.SESSION_CONTINUITY
            },
            {
                'pattern': ['commit', 'git', 'file', 'change'],
                'domain': MemoryDomain.DEVELOPMENT_HISTORY
            }
        ]
    
    async def migrate_memories(
        self, 
        legacy_memories: List[LegacyMemory]
    ) -> MigrationReport:
        """
        Migrate a list of legacy memories to enhanced architecture.
        
        Args:
            legacy_memories: List of legacy memories to migrate
            
        Returns:
            Migration report with results and statistics
        """
        start_time = datetime.now()
        report = MigrationReport()
        report.total_legacy_memories = len(legacy_memories)
        
        self.logger.info(f"Starting migration of {len(legacy_memories)} memories")
        
        # Process memories in batches for better performance
        batch_size = 50
        for i in range(0, len(legacy_memories), batch_size):
            batch = legacy_memories[i:i + batch_size]
            await self._process_migration_batch(batch, report)
            
            # Log progress
            if i % (batch_size * 10) == 0:
                self.logger.info(
                    f"Migration progress: {i + len(batch)}/{len(legacy_memories)} "
                    f"({(i + len(batch)) / len(legacy_memories) * 100:.1f}%)"
                )
        
        # Finalize report
        duration = (datetime.now() - start_time).total_seconds()
        report.finalize(duration)
        
        self.logger.info(
            f"Migration completed: {report.successfully_migrated}/{report.total_legacy_memories} "
            f"memories in {duration:.2f}s ({report.memories_per_second:.1f} mem/s)"
        )
        
        return report
    
    async def _process_migration_batch(
        self, 
        batch: List[LegacyMemory], 
        report: MigrationReport
    ) -> None:
        """Process a batch of legacy memories for migration."""
        enhanced_memories = []
        
        for legacy_memory in batch:
            try:
                # Convert legacy memory to enhanced memory
                enhanced_memory = self._convert_legacy_to_enhanced(legacy_memory)
                enhanced_memories.append(enhanced_memory)
                
                # Update report counters
                report.successfully_migrated += 1
                
                # Update hierarchy counters
                if legacy_memory.hierarchy_level == 0:
                    report.l0_migrated += 1
                elif legacy_memory.hierarchy_level == 1:
                    report.l1_migrated += 1
                elif legacy_memory.hierarchy_level == 2:
                    report.l2_migrated += 1
                
                # Update temporal window counters
                if enhanced_memory.temporal_window == TemporalWindow.ACTIVE:
                    report.active_memories += 1
                elif enhanced_memory.temporal_window == TemporalWindow.WORKING:
                    report.working_memories += 1
                elif enhanced_memory.temporal_window == TemporalWindow.REFERENCE:
                    report.reference_memories += 1
                elif enhanced_memory.temporal_window == TemporalWindow.ARCHIVE:
                    report.archive_memories += 1
                
            except Exception as e:
                error_msg = f"Failed to convert memory {legacy_memory.id}: {e}"
                report.add_error(error_msg)
                self.logger.error(error_msg)
                continue
        
        # Store batch of enhanced memories
        if enhanced_memories:
            try:
                await self.enhanced_storage.store_memories_batch(enhanced_memories)
            except Exception as e:
                error_msg = f"Failed to store memory batch: {e}"
                report.add_error(error_msg)
                self.logger.error(error_msg)
    
    def _convert_legacy_to_enhanced(
        self, 
        legacy_memory: LegacyMemory
    ) -> EnhancedCognitiveMemory:
        """Convert a single legacy memory to enhanced architecture."""
        
        # Determine temporal window based on hierarchy and conditions
        temporal_window = self._determine_temporal_window(legacy_memory)
        
        # Infer semantic domain from content
        semantic_domain = self._infer_semantic_domain(legacy_memory)
        
        # Create enhanced memory
        enhanced_memory = EnhancedCognitiveMemory(
            id=legacy_memory.id,
            content=legacy_memory.content,
            
            # Temporal classification
            temporal_window=temporal_window,
            window_transition_date=None,  # Will be calculated automatically
            
            # Semantic organization
            semantic_domain=semantic_domain,
            auto_discovered_clusters=set(),  # Will be populated later
            user_defined_tags=legacy_memory.tags,
            
            # Preserve existing temporal metadata
            created_date=legacy_memory.created_date,
            last_accessed=legacy_memory.last_accessed,
            last_modified=legacy_memory.last_accessed,  # Assume modified when accessed
            
            # Preserve access and relevance data
            access_count=legacy_memory.access_count,
            importance_score=legacy_memory.importance_score,
            relevance_decay_rate=0.1,  # Default value
            
            # Preserve compatibility fields
            memory_type=legacy_memory.memory_type,
            strength=legacy_memory.strength,
            metadata=legacy_memory.metadata.copy()
        )
        
        # Add migration metadata
        enhanced_memory.metadata['migration_info'] = {
            'source_hierarchy_level': legacy_memory.hierarchy_level,
            'migration_date': datetime.now().isoformat(),
            'migration_version': '1.0'
        }
        
        return enhanced_memory
    
    def _determine_temporal_window(
        self, 
        legacy_memory: LegacyMemory
    ) -> TemporalWindow:
        """Determine the appropriate temporal window for a legacy memory."""
        
        level = legacy_memory.hierarchy_level
        mapping_rule = self.temporal_mapping_rules.get(level, {})
        default_window = mapping_rule.get('default_window', TemporalWindow.WORKING)
        conditions = mapping_rule.get('conditions', {})
        
        # Calculate age and access patterns
        now = datetime.now()
        age_days = (now - legacy_memory.created_date).days
        days_since_access = (now - legacy_memory.last_accessed).days
        
        # Apply condition-based rules
        
        # Very recent access (within 1 day)
        if days_since_access <= 1 and 'very_recent' in conditions:
            return conditions['very_recent']
        
        # Recent access (within 7 days)
        if days_since_access <= 7 and 'recent_access' in conditions:
            return conditions['recent_access']
        
        # Old and unused (over 90 days old, not accessed in 30 days)
        if (age_days > 90 and days_since_access > 30 and 
            'old_unused' in conditions):
            return conditions['old_unused']
        
        # Old (over 60 days)
        if age_days > 60 and 'old' in conditions:
            return conditions['old']
        
        # Important memories (high access count or importance score)
        if ((legacy_memory.access_count > 5 or legacy_memory.importance_score > 0.7) and
            'important' in conditions):
            return conditions['important']
        
        # Default mapping
        return default_window
    
    def _infer_semantic_domain(
        self, 
        legacy_memory: LegacyMemory
    ) -> MemoryDomain:
        """Infer the semantic domain based on memory content and metadata."""
        
        content_lower = legacy_memory.content.lower()
        
        # Check against inference rules
        for rule in self.domain_inference_rules:
            pattern_matches = sum(
                1 for pattern in rule['pattern']
                if pattern in content_lower
            )
            
            # If majority of patterns match, assign this domain
            if pattern_matches >= len(rule['pattern']) / 2:
                return rule['domain']
        
        # Check tags for domain hints
        tags_lower = {tag.lower() for tag in legacy_memory.tags}
        
        if any(tag in tags_lower for tag in ['project', 'status', 'milestone']):
            return MemoryDomain.PROJECT_CONTEXT
        elif any(tag in tags_lower for tag in ['code', 'architecture', 'pattern']):
            return MemoryDomain.TECHNICAL_PATTERNS
        elif any(tag in tags_lower for tag in ['decision', 'rationale']):
            return MemoryDomain.DECISION_CHAINS
        elif any(tag in tags_lower for tag in ['session', 'handoff']):
            return MemoryDomain.SESSION_CONTINUITY
        elif any(tag in tags_lower for tag in ['git', 'commit', 'development']):
            return MemoryDomain.DEVELOPMENT_HISTORY
        
        # Default domain
        return MemoryDomain.AI_INTERACTIONS


class MigrationOrchestrator:
    """
    High-level orchestrator for the complete migration process.
    
    This class coordinates the entire migration workflow from legacy
    Heimdall to enhanced architecture.
    """
    
    def __init__(
        self,
        legacy_bridge: LegacyHeimdallBridge,
        migration_engine: EnhancedMigrationEngine,
        logger: Optional[logging.Logger] = None
    ):
        """Initialize the migration orchestrator."""
        self.legacy_bridge = legacy_bridge
        self.migration_engine = migration_engine
        self.logger = logger or logging.getLogger(__name__)
    
    async def run_full_migration(
        self,
        dry_run: bool = False,
        backup_legacy_data: bool = True
    ) -> MigrationReport:
        """
        Run the complete migration process.
        
        Args:
            dry_run: If True, analyze migration without actually storing data
            backup_legacy_data: If True, create backup of legacy data
            
        Returns:
            Migration report with results and statistics
        """
        self.logger.info("Starting full Heimdall migration process")
        
        try:
            # Step 1: Extract legacy memories
            self.logger.info("Step 1: Extracting legacy memories...")
            legacy_memories = await self.legacy_bridge.extract_all_legacy_memories()
            
            if not legacy_memories:
                self.logger.warning("No legacy memories found to migrate")
                return MigrationReport()
            
            # Step 2: Create backup if requested
            if backup_legacy_data and not dry_run:
                self.logger.info("Step 2: Creating legacy data backup...")
                await self._create_legacy_backup(legacy_memories)
            
            # Step 3: Run migration
            if dry_run:
                self.logger.info("Step 3: Running migration analysis (dry run)...")
                report = await self._analyze_migration(legacy_memories)
            else:
                self.logger.info("Step 3: Running full migration...")
                report = await self.migration_engine.migrate_memories(legacy_memories)
            
            # Step 4: Generate migration summary
            self._log_migration_summary(report)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            report = MigrationReport()
            report.add_error(f"Migration process failed: {e}")
            return report
    
    async def _create_legacy_backup(
        self, 
        legacy_memories: List[LegacyMemory]
    ) -> None:
        """Create a backup of legacy memory data."""
        try:
            backup_data = {
                'backup_timestamp': datetime.now().isoformat(),
                'total_memories': len(legacy_memories),
                'memories': [
                    {
                        'id': memory.id,
                        'content': memory.content,
                        'hierarchy_level': memory.hierarchy_level,
                        'memory_type': memory.memory_type,
                        'strength': memory.strength,
                        'created_date': memory.created_date.isoformat(),
                        'last_accessed': memory.last_accessed.isoformat(),
                        'access_count': memory.access_count,
                        'importance_score': memory.importance_score,
                        'metadata': memory.metadata,
                        'tags': list(memory.tags)
                    }
                    for memory in legacy_memories
                ]
            }
            
            backup_path = Path(f"heimdall_legacy_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Legacy data backup created: {backup_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to create legacy backup: {e}")
    
    async def _analyze_migration(
        self, 
        legacy_memories: List[LegacyMemory]
    ) -> MigrationReport:
        """Analyze what the migration would do without actually migrating."""
        report = MigrationReport()
        report.total_legacy_memories = len(legacy_memories)
        
        # Simulate migration to gather statistics
        for legacy_memory in legacy_memories:
            try:
                # Simulate conversion
                enhanced_memory = self.migration_engine._convert_legacy_to_enhanced(
                    legacy_memory
                )
                
                # Update counters
                report.successfully_migrated += 1
                
                if legacy_memory.hierarchy_level == 0:
                    report.l0_migrated += 1
                elif legacy_memory.hierarchy_level == 1:
                    report.l1_migrated += 1
                elif legacy_memory.hierarchy_level == 2:
                    report.l2_migrated += 1
                
                if enhanced_memory.temporal_window == TemporalWindow.ACTIVE:
                    report.active_memories += 1
                elif enhanced_memory.temporal_window == TemporalWindow.WORKING:
                    report.working_memories += 1
                elif enhanced_memory.temporal_window == TemporalWindow.REFERENCE:
                    report.reference_memories += 1
                elif enhanced_memory.temporal_window == TemporalWindow.ARCHIVE:
                    report.archive_memories += 1
                
            except Exception as e:
                report.add_error(f"Would fail to convert memory {legacy_memory.id}: {e}")
        
        return report
    
    def _log_migration_summary(self, report: MigrationReport) -> None:
        """Log a comprehensive migration summary."""
        self.logger.info("=" * 60)
        self.logger.info("MIGRATION SUMMARY")
        self.logger.info("=" * 60)
        
        self.logger.info(f"Total memories processed: {report.total_legacy_memories}")
        self.logger.info(f"Successfully migrated: {report.successfully_migrated}")
        self.logger.info(f"Failed migrations: {report.failed_migrations}")
        
        if report.total_legacy_memories > 0:
            success_rate = (report.successfully_migrated / report.total_legacy_memories) * 100
            self.logger.info(f"Success rate: {success_rate:.1f}%")
        
        self.logger.info("\nHierarchy breakdown:")
        self.logger.info(f"  L0 (Concepts) -> {report.l0_migrated}")
        self.logger.info(f"  L1 (Contexts) -> {report.l1_migrated}")  
        self.logger.info(f"  L2 (Episodes) -> {report.l2_migrated}")
        
        self.logger.info("\nTemporal window distribution:")
        self.logger.info(f"  ACTIVE: {report.active_memories}")
        self.logger.info(f"  WORKING: {report.working_memories}")
        self.logger.info(f"  REFERENCE: {report.reference_memories}")
        self.logger.info(f"  ARCHIVE: {report.archive_memories}")
        
        self.logger.info(f"\nMigration completed in {report.migration_duration:.2f}s")
        self.logger.info(f"Processing rate: {report.memories_per_second:.1f} memories/second")
        
        if report.warnings:
            self.logger.info(f"\nWarnings ({len(report.warnings)}):")
            for warning in report.warnings[:5]:  # Show first 5 warnings
                self.logger.info(f"  - {warning}")
            if len(report.warnings) > 5:
                self.logger.info(f"  ... and {len(report.warnings) - 5} more")
        
        if report.errors:
            self.logger.info(f"\nErrors ({len(report.errors)}):")
            for error in report.errors[:5]:  # Show first 5 errors
                self.logger.info(f"  - {error}")
            if len(report.errors) > 5:
                self.logger.info(f"  ... and {len(report.errors) - 5} more")
        
        self.logger.info("=" * 60)