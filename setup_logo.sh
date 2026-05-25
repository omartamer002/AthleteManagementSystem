#!/bin/bash
# Quick setup for Tiger Academy Report Logo

echo "🐯 Tiger Academy Logo Setup"
echo "================================"

# Create the logo directory
echo "📁 Creating logo directory..."
mkdir -p backend/static/img

echo ""
echo "✅ Directory created: backend/static/img/"
echo ""
echo "📝 NEXT STEP:"
echo "   Please save your tiger logo as:"
echo "   backend/static/img/tiger_logo.png"
echo ""
echo "📋 Logo Requirements:"
echo "   - Format: PNG with transparency"
echo "   - Recommended size: 58x58 pixels"
echo "   - Color: White/light color (appears on black background)"
echo ""
echo "🧪 After saving the logo, test with:"
echo "   python3 manage.py shell < test_logo.py"
echo ""
echo "📚 For detailed setup: See LOGO_SETUP_GUIDE.md"
