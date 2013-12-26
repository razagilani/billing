<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:fn="http://www.w3.org/2005/xpath-functions">
	<xsl:output method="html" version="4.01" encoding="UTF-8" indent="yes"/>
	

<xsl:template match="/">
  <html>
  <body>
		  <h1>Account Number: <xsl:value-of select="utilitybill/car/accountnumber"/></h1>
  
		 <table border="1">
				<tbody>
					<caption>Uncategorized Addresses </caption>
					<tr>
						<th></th><th></th>
					</tr>
					 <xsl:for-each select="/utilitybill">
						<xsl:apply-templates select="unknownaddress"/>
					</xsl:for-each>
				</tbody>
		</table>
		
		 <table border="1">
				<tbody>
					<caption>Service Address</caption>
					<tr>
						<th></th><th></th>
					</tr>
					 <xsl:for-each select="/utilitybill/car">
						<xsl:apply-templates select="serviceaddress"/>
					</xsl:for-each>
				</tbody>
		</table>



  </body>
  </html>
</xsl:template>

	<xsl:template match="serviceaddress | unknownaddress">
		<tr>
			<td colspan="2"><xsl:value-of select="@description"/></td>
		</tr>
		<tr>
			<td>Addressee</td>
			<td><xsl:value-of select="addressee"/></td>
		</tr>
		<tr>
			<td>Street</td>
			<td><xsl:value-of select="street"/></td>
		</tr>
		<tr>
			<td>City</td>
			<td><xsl:value-of select="city"/></td>
		</tr>
		<tr>
			<td>State</td>
			<td><xsl:value-of select="state"/></td>
		</tr>
		<tr>
			<td>Postal Code</td>
			<td><xsl:value-of select="postalcode"/></td>
		</tr>
		<tr>
			<td>Country</td>
			<td><xsl:value-of select="country"/></td>
		</tr>
	</xsl:template>

</xsl:stylesheet>
