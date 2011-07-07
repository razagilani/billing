<?xml version="1.0" encoding="UTF-8"?>
<structure version="9" htmlmode="strict" relativeto="*SPS" encodinghtml="UTF-8" encodingrtf="ISO-8859-1" encodingpdf="UTF-8" useimportschema="1" embed-images="1" ShowDesignMarkups="2">
	<parameters/>
	<schemasources>
		<namespaces>
			<nspair prefix="sb" uri="skylinebill"/>
			<nspair prefix="ub" uri="utilitybill"/>
		</namespaces>
		<schemasources>
			<xsdschemasource name="XML" main="1" schemafile="C:\workspace-skyline\billing\UtilityBill.xsd" workingxmlfile="C:\workspace-skyline\billing\sample\Skyline-Pepco-3091-4490-03-20080908.xml">
				<xmltablesupport/>
				<textstateicons/>
			</xsdschemasource>
		</schemasources>
	</schemasources>
	<modules/>
	<flags>
		<scripts/>
		<globalparts/>
		<designfragments/>
		<pagelayouts/>
	</flags>
	<scripts>
		<script language="javascript"/>
	</scripts>
	<importedxslt/>
	<globalstyles/>
	<mainparts>
		<children>
			<globaltemplate subtype="main" match="/">
				<children>
					<documentsection>
						<properties columncount="1" columngap="0.50in" headerfooterheight="fixed" pagemultiplepages="0" pagenumberingformat="1" pagenumberingstartat="auto" pagestart="next" paperheight="11in" papermarginbottom="0.79in" papermarginfooter="0.30in" papermarginheader="0.30in" papermarginleft="0.60in" papermarginright="0.60in" papermargintop="0.79in" paperwidth="8.50in"/>
					</documentsection>
					<layout-container locksize="1" blueprint-image-url="file:///C:/workspace-skyline/billing/presentation/images/EmeraldCity.png">
						<styles height="5.19in" overflow="hidden" position="relative" width="7.71in"/>
						<children>
							<textbox autoresize="1" additional-width="0.92in" additional-height="0.72in">
								<styles height="0.92in" left="0.40in" overflow="hidden" padding="2px" position="absolute" top="0.40in" width="3.08in"/>
								<children>
									<template subtype="source" match="XML">
										<children>
											<template subtype="element" match="ub:utilitybill">
												<children>
													<template subtype="element" match="ub:car">
														<children>
															<template subtype="element" match="ub:billingaddress">
																<children>
																	<content/>
																</children>
																<variables/>
															</template>
														</children>
														<variables/>
													</template>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
							</textbox>
							<textbox autoresize="1" additional-width="20%" additional-height="10%">
								<styles height="1.85in" left="0in" overflow="hidden" padding="2px" position="absolute" top="3.40in" width="6.24in"/>
								<children>
									<template subtype="element" match="ub:utilitybill">
										<children>
											<template subtype="element" match="ub:details">
												<children>
													<tgrid>
														<properties border="1"/>
														<styles font-size="xx-small"/>
														<children>
															<tgridbody-cols>
																<children>
																	<tgridcol/>
																	<tgridcol/>
																	<tgridcol/>
																	<tgridcol/>
																</children>
															</tgridbody-cols>
															<tgridheader-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<text fixtext="service">
																						<styles font-size="small"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<text fixtext="rateschedule">
																						<styles font-size="small"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<text fixtext="Charges">
																						<styles font-size="small"/>
																					</text>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<text fixtext="total">
																						<styles font-size="small"/>
																					</text>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridheader-rows>
															<tgridbody-rows>
																<children>
																	<tgridrow>
																		<children>
																			<tgridcell>
																				<children>
																					<template subtype="attribute" match="service">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="ub:rateschedule">
																						<children>
																							<content/>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="ub:chargegroup">
																						<children>
																							<tgrid>
																								<properties border="1"/>
																								<children>
																									<tgridbody-cols>
																										<children>
																											<tgridcol/>
																											<tgridcol/>
																											<tgridcol/>
																										</children>
																									</tgridbody-cols>
																									<tgridheader-rows>
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<text fixtext="type">
																																<styles font-size="small"/>
																															</text>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<text fixtext="charges">
																																<styles font-size="small"/>
																															</text>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<text fixtext="subtotal">
																																<styles font-size="small"/>
																															</text>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																									</tgridheader-rows>
																									<tgridbody-rows>
																										<children>
																											<tgridrow>
																												<children>
																													<tgridcell>
																														<children>
																															<template subtype="attribute" match="type">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:charges">
																																<children>
																																	<content/>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																													<tgridcell>
																														<children>
																															<template subtype="element" match="ub:subtotal">
																																<children>
																																	<content>
																																		<format datatype="decimal"/>
																																	</content>
																																</children>
																																<variables/>
																															</template>
																														</children>
																													</tgridcell>
																												</children>
																											</tgridrow>
																										</children>
																									</tgridbody-rows>
																								</children>
																							</tgrid>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																			<tgridcell>
																				<children>
																					<template subtype="element" match="ub:total">
																						<children>
																							<content>
																								<format datatype="decimal"/>
																							</content>
																						</children>
																						<variables/>
																					</template>
																				</children>
																			</tgridcell>
																		</children>
																	</tgridrow>
																</children>
															</tgridbody-rows>
														</children>
													</tgrid>
												</children>
												<variables/>
											</template>
										</children>
										<variables/>
									</template>
								</children>
							</textbox>
						</children>
					</layout-container>
				</children>
			</globaltemplate>
		</children>
	</mainparts>
	<globalparts/>
	<pagelayout>
		<properties paperheight="11.69in" paperwidth="8.27in"/>
	</pagelayout>
	<designfragments/>
</structure>
