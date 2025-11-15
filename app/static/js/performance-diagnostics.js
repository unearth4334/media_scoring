/**
 * Performance Diagnostics Tool for Media Scoring Application
 * 
 * Measures and reports performance metrics to identify bottlenecks,
 * especially for mobile devices with limited RAM/CPU.
 */

class PerformanceDiagnostics {
  constructor() {
    this.metrics = {};
    this.measurements = [];
    this.isEnabled = false;
    this.logToConsole = true;
    this.logToServer = false;
  }

  /**
   * Initialize performance monitoring
   */
  init() {
    this.isEnabled = true;
    this.detectDevice();
    this.measureBaseline();
    this.setupObservers();
    console.log('[PERF] Performance diagnostics initialized');
  }

  /**
   * Detect device capabilities
   */
  detectDevice() {
    const nav = navigator;
    this.metrics.device = {
      userAgent: nav.userAgent,
      platform: nav.platform,
      hardwareConcurrency: nav.hardwareConcurrency || 'unknown',
      deviceMemory: nav.deviceMemory || 'unknown', // GB (Chrome only)
      maxTouchPoints: nav.maxTouchPoints || 0,
      isMobile: /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(nav.userAgent),
      screenWidth: window.screen.width,
      screenHeight: window.screen.height,
      viewportWidth: window.innerWidth,
      viewportHeight: window.innerHeight,
      pixelRatio: window.devicePixelRatio || 1,
      connection: this.getConnectionInfo()
    };

    // Estimate device tier (low/mid/high)
    const memory = nav.deviceMemory || 4;
    const cores = nav.hardwareConcurrency || 4;
    if (memory <= 2 || cores <= 2) {
      this.metrics.device.tier = 'low';
    } else if (memory <= 4 || cores <= 4) {
      this.metrics.device.tier = 'mid';
    } else {
      this.metrics.device.tier = 'high';
    }

    console.log('[PERF] Device:', this.metrics.device);
  }

  /**
   * Get network connection info
   */
  getConnectionInfo() {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (!conn) return { type: 'unknown' };

    return {
      type: conn.effectiveType || 'unknown', // '4g', '3g', '2g', 'slow-2g'
      downlink: conn.downlink || 'unknown', // Mbps
      rtt: conn.rtt || 'unknown', // ms
      saveData: conn.saveData || false
    };
  }

  /**
   * Measure baseline performance metrics
   */
  measureBaseline() {
    // Memory (Chrome only)
    if (performance.memory) {
      this.metrics.memory = {
        usedJSHeapSize: Math.round(performance.memory.usedJSHeapSize / 1048576), // MB
        totalJSHeapSize: Math.round(performance.memory.totalJSHeapSize / 1048576), // MB
        jsHeapSizeLimit: Math.round(performance.memory.jsHeapSizeLimit / 1048576) // MB
      };
    }

    // Initial page load
    if (performance.timing) {
      const timing = performance.timing;
      this.metrics.pageLoad = {
        domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
        loadComplete: timing.loadEventEnd - timing.navigationStart,
        domReady: timing.domComplete - timing.domLoading,
        responseTime: timing.responseEnd - timing.requestStart
      };
    }

    console.log('[PERF] Baseline metrics:', this.metrics);
  }

  /**
   * Setup performance observers
   */
  setupObservers() {
    // Long tasks observer (Chrome only)
    if ('PerformanceObserver' in window) {
      try {
        const longTaskObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            this.recordMeasurement('long-task', {
              name: entry.name,
              duration: entry.duration,
              startTime: entry.startTime
            });
            console.warn(`[PERF] Long task detected: ${entry.duration}ms`);
          }
        });
        longTaskObserver.observe({ entryTypes: ['longtask'] });
      } catch (e) {
        // Long task API not supported
      }

      // Layout shifts observer
      try {
        const clsObserver = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (entry.hadRecentInput) continue; // Ignore user-caused shifts
            this.recordMeasurement('layout-shift', {
              value: entry.value,
              time: entry.startTime
            });
          }
        });
        clsObserver.observe({ entryTypes: ['layout-shift'] });
      } catch (e) {
        // Layout shift API not supported
      }
    }
  }

  /**
   * Start timing a specific operation
   */
  startTimer(label) {
    if (!this.isEnabled) return;
    performance.mark(`${label}-start`);
  }

  /**
   * End timing and record measurement
   */
  endTimer(label, metadata = {}) {
    if (!this.isEnabled) return;
    
    try {
      performance.mark(`${label}-end`);
      performance.measure(label, `${label}-start`, `${label}-end`);
      
      const measure = performance.getEntriesByName(label)[0];
      const duration = measure.duration;

      this.recordMeasurement(label, {
        duration,
        ...metadata
      });

      // Warn on slow operations
      const thresholds = {
        'api-fetch': 1000,
        'render-sidebar': 500,
        'apply-filter': 200,
        'dom-update': 100,
        'thumbnail-load': 500
      };

      const threshold = thresholds[label] || 1000;
      if (duration > threshold) {
        console.warn(`[PERF] Slow operation: ${label} took ${duration.toFixed(2)}ms (threshold: ${threshold}ms)`);
      } else {
        console.log(`[PERF] ${label}: ${duration.toFixed(2)}ms`);
      }

      // Cleanup
      performance.clearMarks(`${label}-start`);
      performance.clearMarks(`${label}-end`);
      performance.clearMeasures(label);

      return duration;
    } catch (e) {
      console.error('[PERF] Error measuring:', e);
      return null;
    }
  }

  /**
   * Record a measurement
   */
  recordMeasurement(type, data) {
    this.measurements.push({
      type,
      timestamp: Date.now(),
      ...data
    });

    // Keep only last 100 measurements
    if (this.measurements.length > 100) {
      this.measurements.shift();
    }
  }

  /**
   * Measure DOM complexity
   */
  measureDOMComplexity() {
    const sidebar = document.getElementById('sidebar_list');
    const complexity = {
      sidebarItems: sidebar ? sidebar.querySelectorAll('.item').length : 0,
      totalElements: document.querySelectorAll('*').length,
      images: document.querySelectorAll('img').length,
      videos: document.querySelectorAll('video').length,
      listeners: this.estimateEventListeners()
    };

    this.metrics.domComplexity = complexity;
    console.log('[PERF] DOM Complexity:', complexity);
    return complexity;
  }

  /**
   * Estimate number of event listeners (approximation)
   */
  estimateEventListeners() {
    // This is an approximation - actual count is hard to determine
    const clickables = document.querySelectorAll('[onclick], button, a, .item').length;
    return `~${clickables * 2}`; // Rough estimate
  }

  /**
   * Measure memory usage (Chrome only)
   */
  measureMemory() {
    if (!performance.memory) {
      console.warn('[PERF] Memory API not available');
      return null;
    }

    const memory = {
      usedJSHeapSize: Math.round(performance.memory.usedJSHeapSize / 1048576), // MB
      totalJSHeapSize: Math.round(performance.memory.totalJSHeapSize / 1048576), // MB
      jsHeapSizeLimit: Math.round(performance.memory.jsHeapSizeLimit / 1048576), // MB
      percentUsed: ((performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100).toFixed(1)
    };

    console.log('[PERF] Memory:', memory);
    
    // Warn if memory usage is high
    if (memory.percentUsed > 80) {
      console.error(`[PERF] HIGH MEMORY USAGE: ${memory.percentUsed}% of heap limit!`);
    } else if (memory.percentUsed > 60) {
      console.warn(`[PERF] Elevated memory usage: ${memory.percentUsed}% of heap limit`);
    }

    return memory;
  }

  /**
   * Measure FPS (frames per second)
   */
  measureFPS(duration = 2000) {
    return new Promise((resolve) => {
      let frameCount = 0;
      const startTime = performance.now();
      let lastTime = startTime;

      const countFrame = (currentTime) => {
        frameCount++;
        if (currentTime - startTime < duration) {
          requestAnimationFrame(countFrame);
        } else {
          const fps = Math.round((frameCount * 1000) / (currentTime - startTime));
          console.log(`[PERF] FPS: ${fps} (${frameCount} frames in ${duration}ms)`);
          
          if (fps < 30) {
            console.error(`[PERF] LOW FPS: ${fps} fps (target: 60 fps)`);
          } else if (fps < 50) {
            console.warn(`[PERF] Below target FPS: ${fps} fps (target: 60 fps)`);
          }
          
          resolve(fps);
        }
      };

      requestAnimationFrame(countFrame);
    });
  }

  /**
   * Test scroll performance
   */
  async testScrollPerformance() {
    console.log('[PERF] Testing scroll performance...');
    const sidebar = document.getElementById('sidebar_list');
    if (!sidebar) {
      console.error('[PERF] Sidebar not found');
      return;
    }

    // Measure FPS during scroll
    const scrollTest = new Promise((resolve) => {
      let frameCount = 0;
      let totalDuration = 0;
      const maxFrames = 60;

      const measureFrame = () => {
        const start = performance.now();
        
        if (frameCount < maxFrames) {
          frameCount++;
          requestAnimationFrame(() => {
            const duration = performance.now() - start;
            totalDuration += duration;
            measureFrame();
          });
        } else {
          const avgFrameTime = totalDuration / frameCount;
          const fps = 1000 / avgFrameTime;
          resolve({ fps: fps.toFixed(1), avgFrameTime: avgFrameTime.toFixed(2) });
        }
      };

      // Trigger scroll
      sidebar.scrollTop = 100;
      measureFrame();
    });

    const result = await scrollTest;
    console.log(`[PERF] Scroll performance: ${result.fps} FPS (avg frame time: ${result.avgFrameTime}ms)`);
    return result;
  }

  /**
   * Generate performance report
   */
  generateReport() {
    const report = {
      timestamp: new Date().toISOString(),
      device: this.metrics.device,
      memory: this.measureMemory(),
      dom: this.measureDOMComplexity(),
      recentMeasurements: this.measurements.slice(-20),
      summary: this.generateSummary()
    };

    console.log('[PERF] ===== PERFORMANCE REPORT =====');
    console.log(JSON.stringify(report, null, 2));
    console.log('[PERF] ================================');

    return report;
  }

  /**
   * Generate performance summary with recommendations
   */
  generateSummary() {
    const issues = [];
    const recommendations = [];

    // Check device tier
    if (this.metrics.device.tier === 'low') {
      issues.push('Low-end device detected');
      recommendations.push('Reduce page size to 50 items');
      recommendations.push('Disable thumbnails on mobile');
      recommendations.push('Use placeholder images');
    }

    // Check memory
    if (performance.memory) {
      const percentUsed = (performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100;
      if (percentUsed > 80) {
        issues.push(`High memory usage: ${percentUsed.toFixed(1)}%`);
        recommendations.push('Reduce DOM nodes (use virtual scrolling)');
        recommendations.push('Clear unused data/images');
      }
    }

    // Check DOM complexity
    const dom = this.measureDOMComplexity();
    if (dom.sidebarItems > 200) {
      issues.push(`Too many DOM nodes: ${dom.sidebarItems} sidebar items`);
      recommendations.push('Implement virtual scrolling');
      recommendations.push('Reduce page size');
    }

    // Check slow operations
    const slowOps = this.measurements.filter(m => m.duration > 500);
    if (slowOps.length > 0) {
      issues.push(`${slowOps.length} slow operations detected`);
      recommendations.push('Optimize render functions');
      recommendations.push('Defer non-critical operations');
    }

    return {
      deviceTier: this.metrics.device.tier,
      issues,
      recommendations,
      health: issues.length === 0 ? 'good' : issues.length < 3 ? 'fair' : 'poor'
    };
  }

  /**
   * Send report to server
   */
  async sendReportToServer(report) {
    if (!this.logToServer) return;

    try {
      await fetch('/api/performance-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report)
      });
      console.log('[PERF] Report sent to server');
    } catch (e) {
      console.error('[PERF] Failed to send report:', e);
    }
  }

  /**
   * Run comprehensive performance test
   */
  async runFullTest() {
    console.log('[PERF] ===== STARTING FULL PERFORMANCE TEST =====');
    
    // 1. Measure memory before
    console.log('[PERF] Step 1: Measure initial memory');
    const memoryBefore = this.measureMemory();
    
    // 2. Measure DOM complexity
    console.log('[PERF] Step 2: Measure DOM complexity');
    const domComplexity = this.measureDOMComplexity();
    
    // 3. Test scroll performance
    console.log('[PERF] Step 3: Test scroll performance');
    const scrollPerf = await this.testScrollPerformance();
    
    // 4. Measure FPS
    console.log('[PERF] Step 4: Measure FPS (2 second test)');
    const fps = await this.measureFPS(2000);
    
    // 5. Measure memory after
    console.log('[PERF] Step 5: Measure memory after test');
    const memoryAfter = this.measureMemory();
    
    // 6. Generate report
    console.log('[PERF] Step 6: Generate report');
    const report = this.generateReport();
    
    console.log('[PERF] ===== TEST COMPLETE =====');
    console.log('[PERF] Summary:', report.summary);
    
    return report;
  }
}

// Create global instance
window.perfDiag = new PerformanceDiagnostics();

// Auto-initialize on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    window.perfDiag.init();
  });
} else {
  window.perfDiag.init();
}

// Add helper methods to window for easy console access
window.perfTest = () => window.perfDiag.runFullTest();
window.perfReport = () => window.perfDiag.generateReport();
window.perfMemory = () => window.perfDiag.measureMemory();
window.perfFPS = () => window.perfDiag.measureFPS(2000);
window.perfDOM = () => window.perfDiag.measureDOMComplexity();

console.log('[PERF] Performance diagnostics loaded. Use perfTest() to run full test.');
