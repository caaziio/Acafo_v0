const express = require('express');
const puppeteer = require('puppeteer');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 3001;

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.static('public'));

// Test endpoint
app.get('/test', (req, res) => {
  res.json({ message: 'Server is working!' });
});

// Debug endpoint to see what HTML is being sent
app.post('/debug-html', (req, res) => {
  try {
    const { html, filename } = req.body;
    console.log('=== Debug HTML Received ===');
    console.log('HTML length:', html ? html.length : 'undefined');
    console.log('Filename:', filename);
    console.log('HTML preview:', html ? html.substring(0, 1000) : 'No HTML');
    
    res.json({ 
      received: true, 
      htmlLength: html ? html.length : 0,
      filename: filename,
      htmlPreview: html ? html.substring(0, 500) : 'No HTML'
    });
  } catch (error) {
    console.error('Debug error:', error);
    res.status(500).json({ error: error.message });
  }
});

// PDF Generation Endpoint
app.post('/generate-pdf', async (req, res) => {
  let browser;
  try {
    const { html, filename = 'resume.pdf' } = req.body;
    
    if (!html) {
      return res.status(400).json({ error: 'HTML content is required' });
    }

    console.log('=== PDF Generation Started ===');
    console.log('HTML length:', html.length);
    console.log('Filename:', filename);
    console.log('HTML preview (first 500 chars):', html.substring(0, 500));

    // Launch browser with minimal options
    console.log('Launching browser...');
    try {
      browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox']
      });
    } catch (launchError) {
      console.error('Failed to launch with default options:', launchError.message);
      console.log('Trying with system Chrome...');
      
      // Try with system Chrome on macOS
      browser = await puppeteer.launch({
        headless: true,
        executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
      });
    }

    console.log('Browser launched successfully');

    const page = await browser.newPage();
    console.log('Page created');
    
    // Set content
    console.log('Setting HTML content...');
    await page.setContent(html);
    console.log('HTML content set');

    // Wait a bit
    console.log('Waiting 1 second...');
    await new Promise(resolve => setTimeout(resolve, 1000));
    console.log('Waited 1 second');

    console.log('Generating PDF...');
    const pdf = await page.pdf({
      format: 'A4',
      printBackground: true
    });

    console.log('PDF generated successfully, size:', pdf.length);
    
    // Check if PDF is valid
    if (!pdf || pdf.length === 0) {
      throw new Error('Generated PDF is empty or invalid');
    }
    
    console.log('PDF data type:', typeof pdf);
    console.log('PDF is Buffer:', Buffer.isBuffer(pdf));
    console.log('PDF first 100 bytes:', pdf.slice(0, 100));
    
    // Verify PDF starts with correct header
    const pdfHeader = pdf.slice(0, 4);
    console.log('PDF header bytes:', Array.from(pdfHeader));
    console.log('PDF header as string:', pdfHeader.toString());
    
    // Check if first 4 bytes are %PDF (37, 80, 68, 70 in ASCII)
    if (pdfHeader[0] !== 37 || pdfHeader[1] !== 80 || pdfHeader[2] !== 68 || pdfHeader[3] !== 70) {
      throw new Error('Generated file is not a valid PDF (wrong header)');
    }
    
    console.log('PDF header validation passed');

    // Set response headers
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.setHeader('Content-Length', pdf.length);
    res.setHeader('Cache-Control', 'no-cache');
    
    // Send PDF as binary data
    res.end(pdf);
    console.log('PDF sent to client');

  } catch (error) {
    console.error('=== PDF Generation Error ===');
    console.error('Error message:', error.message);
    console.error('Error stack:', error.stack);
    
    res.status(500).json({ 
      error: 'Failed to generate PDF',
      details: error.message,
      stack: error.stack
    });
  } finally {
    if (browser) {
      try {
        await browser.close();
        console.log('Browser closed');
      } catch (closeError) {
        console.error('Error closing browser:', closeError);
      }
    }
  }
});

// Test PDF endpoint
app.get('/test-pdf', async (req, res) => {
  let browser;
  try {
    console.log('=== Test PDF Generation ===');
    
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox']
    });

    const page = await browser.newPage();
    await page.setContent('<h1>Test PDF</h1><p>This is a test PDF to verify generation works.</p>');
    
    const pdf = await page.pdf({
      format: 'A4',
      printBackground: true
    });

    console.log('Test PDF generated, size:', pdf.length);
    
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'attachment; filename="test.pdf"');
    res.setHeader('Content-Length', pdf.length);
    
    res.send(pdf);
    
  } catch (error) {
    console.error('Test PDF error:', error);
    res.status(500).json({ error: error.message });
  } finally {
    if (browser) await browser.close();
  }
});

// Simple test PDF endpoint
app.get('/simple-pdf', async (req, res) => {
  let browser;
  try {
    console.log('=== Simple PDF Test ===');
    
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox']
    });

    const page = await browser.newPage();
    await page.setContent('<h1>Test PDF</h1><p>This is a simple test.</p>');
    
    const pdf = await page.pdf({
      format: 'A4'
    });

    console.log('Simple PDF generated, size:', pdf.length);
    console.log('PDF header:', pdf.slice(0, 4).toString());
    
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'attachment; filename="test.pdf"');
    res.setHeader('Content-Length', pdf.length);
    res.setHeader('Cache-Control', 'no-cache');
    
    res.end(pdf);
    
  } catch (error) {
    console.error('Simple PDF error:', error);
    res.status(500).json({ error: error.message });
  } finally {
    if (browser) await browser.close();
  }
});

// Minimal PDF test endpoint (hardcoded PDF)
app.get('/minimal-pdf', (req, res) => {
  try {
    console.log('=== Minimal PDF Test ===');
    
    // This is a minimal valid PDF file (just a blank page)
    const minimalPDF = Buffer.from(
      '%PDF-1.4\n' +
      '1 0 obj\n' +
      '<<\n' +
      '  /Type /Catalog\n' +
      '  /Pages 2 0 R\n' +
      '>>\n' +
      'endobj\n' +
      '2 0 obj\n' +
      '<<\n' +
      '  /Type /Pages\n' +
      '  /Kids [3 0 R]\n' +
      '  /Count 1\n' +
      '>>\n' +
      'endobj\n' +
      '3 0 obj\n' +
      '<<\n' +
      '  /Type /Page\n' +
      '  /Parent 2 0 R\n' +
      '  /MediaBox [0 0 612 792]\n' +
      '  /Contents 4 0 R\n' +
      '>>\n' +
      'endobj\n' +
      '4 0 obj\n' +
      '<<\n' +
      '  /Length 44\n' +
      '>>\n' +
      'stream\n' +
      'BT\n' +
      '  /F1 12 Tf\n' +
      '  72 720 Td\n' +
      '  (Hello World) Tj\n' +
      'ET\n' +
      'endstream\n' +
      'endobj\n' +
      'xref\n' +
      '0 5\n' +
      '0000000000 65535 f \n' +
      '0000000009 00000 n \n' +
      '0000000058 00000 n \n' +
      '0000000115 00000 n \n' +
      '0000000204 00000 n \n' +
      'trailer\n' +
      '<<\n' +
      '  /Size 5\n' +
      '  /Root 1 0 R\n' +
      '>>\n' +
      'startxref\n' +
      '297\n' +
      '%%EOF'
    );
    
    console.log('Minimal PDF created, size:', minimalPDF.length);
    console.log('PDF header:', minimalPDF.slice(0, 4).toString());
    
    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'attachment; filename="minimal.pdf"');
    res.setHeader('Content-Length', minimalPDF.length);
    res.setHeader('Cache-Control', 'no-cache');
    
    res.end(minimalPDF);
    
  } catch (error) {
    console.error('Minimal PDF error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'OK', message: 'PDF server is running' });
});

app.listen(PORT, () => {
  console.log(`PDF server running on http://localhost:${PORT}`);
  console.log(`Health check: http://localhost:${PORT}/health`);
  console.log(`Test endpoint: http://localhost:${PORT}/test`);
});
