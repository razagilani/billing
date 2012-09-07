<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:fo="http://www.w3.org/1999/XSL/Format" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:fn="http://www.w3.org/2005/xpath-functions">
	<xsl:output method="text"/>
	
	<xsl:template match="/">
        <xsl:apply-templates/>
   	</xsl:template>
   		
	<xsl:template match="account"><xsl:value-of select="."/></xsl:template>
	<xsl:template match="billseq">-<xsl:value-of select="."/></xsl:template>
	<xsl:template match="addressee">
		<xsl:choose>
			<xsl:when test=". != '' ">,<xsl:value-of select="." /></xsl:when>
			<xsl:otherwise>,No Addressee</xsl:otherwise>
		</xsl:choose>
	</xsl:template>
	<xsl:template match="service">,<xsl:value-of select="."/></xsl:template>
	<xsl:template match="periodbegin">,<xsl:value-of select="."/></xsl:template>
	<xsl:template match="periodend">,<xsl:value-of select="."/></xsl:template>
	<xsl:template match="charge">,<xsl:value-of select="."/><xsl:text>&#13;&#10;</xsl:text></xsl:template>
</xsl:stylesheet>
