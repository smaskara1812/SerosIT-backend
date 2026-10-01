using System;
using System.Data;
using System.Configuration;
using System.Collections;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS_Common;
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.IO;
using CrystalDecisions.CrystalReports.Engine;
using CrystalDecisions.Shared;
using System.Collections.Generic;
using System.Net;
using System.Drawing;
using System.Data.OleDb;
using System.Collections.Generic;
using EBS_Reports.EOS;



public partial class Quality_And_Safety_fmHSE_Drill_Record_Hdr_Details : System.Web.UI.Page
{
    # region User defined variables
    //protected Common_DataRetrival _Common_DataRetrival;
    protected DataSet Ds;
    DataSet DsIncident_Descr = new DataSet();
    SqlConnection Conn;
    SqlDataAdapter Da;
    string strConString = "";
    string strSql = "";
    string ErrorString = "";
    int intImgCnt = 0;
    string[] IMG = new string[10];
    Button[] btnEnableDisable;
    Int16 intMenu_id;
    Int32 intUser_Id;
    public DataTable DtIncident_Img_Path = new DataTable();
    #endregion
    string strScramble = "";
    protected string strDebugModeYN = ConfigurationSettings.AppSettings["DebugModeYN"];

    protected void Page_Load(object sender, EventArgs e)
    {

        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass


        var list = new List<Button>();
        //list.Add(btnAdd);
        //list.Add(btnUpdate);
        list.Add(btnSearch);

        list.Add(btnPrint);
        btnEnableDisable = list.ToArray();
        #endregion
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));
        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt32(Session["User_Id"].ToString());
        # endregion

        if (!IsPostBack)
        {
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Add");
            tbRig_Name.Focus();
        }

        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            Get_Data_For_Edit();
            tbPostbackFlag_Hidden.Value = "";
            Session["Drill_Record_Hdr_Id_Filter"] = tbDrill_Record_Hdr_Id_Hidden.Value;
            frame1.Attributes["src"] = "about:blank";
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");
            btnPrint.Enabled = true;
        }

        #region Open Search Form When Drill Record Hdr_Id
        if (!IsPostBack)
        {
            if (Session["Drill_Record_Hdr_Id_Filter"] != null && Session["Drill_Record_Hdr_Id_Filter"].ToString() != "")
            {
                //ClientScript.RegisterStartupScript(this.GetType(), "Show_Main_Data", " Show_Main_Data();", true);

                tbDrill_Record_Hdr_Id_Hidden.Value = Session["Drill_Record_Hdr_Id_Filter"].ToString();

                Get_Data_For_Edit();
                tbPostbackFlag_Hidden.Value = "";
                Session["Drill_Record_Hdr_Id_Filter"] = tbDrill_Record_Hdr_Id_Hidden.Value;
                frame1.Attributes["src"] = "about:blank";
                EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");
                btnPrint.Enabled = true;
            }
        }
        #endregion

    }


    protected void Get_Data_For_Edit()
    {
        ClearMe(false);
        Conn = new SqlConnection(strConString);
        try
        {

            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_HSE_Drill_Record_Hdr", Conn);
            Da.SelectCommand.Parameters.Clear();
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;

            Da.SelectCommand.Parameters.Add("@Drill_Record_Hdr_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbDrill_Record_Hdr_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select";
            Da.Fill(Ds, "Data_For_Edit");

            tbRig_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Rig"].ToString();
            tbRig_Id_Hidden.Value = Ds.Tables["Data_For_Edit"].Rows[0]["Rig_Id"].ToString();
            tbDrill_Record_No.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Drill_Record_No"].ToString();
            tbDrill_Dt.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Drill_Dt"].ToString();
            tbDrill_Dt_Time.Text = Ds.Tables["Data_For_Edit"].Rows[0]["Drill_Dt_Time"].ToString();
            tbHSE_Drill_Id_1_Name.Text = Ds.Tables["Data_For_Edit"].Rows[0]["HSE_Drill_1"].ToString();
            tbHSE_Drill_Type_2.Text = Ds.Tables["Data_For_Edit"].Rows[0]["HSE_Drill_2"].ToString();


            

        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
                // Conn.Dispose();
            }

        }
    }





    private void ClearMe(bool blnClearMainId)
    {
        if (blnClearMainId == true)
        {
            tbDrill_Record_Hdr_Id_Hidden.Value = "";
        }

        tbRig_Name.Text = "";

        tbDrill_Record_No.Text = "";
        tbDrill_Dt.Text = "";
        tbDrill_Dt_Time.Text = "";

        tbHSE_Drill_Id_1_Name.Text = "";


        tbHSE_Drill_Type_2.Text = "";

        Session["Drill_Record_Hdr_Id_Filter"] = "";

        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");
    }

    protected void btnClear_Click(object sender, EventArgs e)
    {
        ClearMe(true);
    }

    protected void btnEvents_Click(object sender, EventArgs e)
    {
        if (tbDrill_Record_Hdr_Id_Hidden.Value == "")
        { return; }

        // Page.RegisterStartupScript("Change_Color_1", "<script>Change_Color(" + btnEvents.ClientID + ");</script>");

        string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();
        frame1.Attributes["src"] = strAuth_Sign_Photo_URL + "/Quality And Safety/Drills/frmHSE_Drill_Record_Event.aspx?A=" + strScramble + "&B=" + clsMiscellaneous.encryptQueryString(tbDrill_Record_Hdr_Id_Hidden.Value)

            + "&C=" + clsMiscellaneous.encryptQueryString(tbDrill_Dt.Text);
    }
    protected void btnObservations_Click(object sender, EventArgs e)
    {
        if (tbDrill_Record_Hdr_Id_Hidden.Value == "")
        { return; }

        // Page.RegisterStartupScript("Change_Color_1", "<script>Change_Color(" + btnEvents.ClientID + ");</script>");

        string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();
        frame1.Attributes["src"] = strAuth_Sign_Photo_URL + "/Quality And Safety/Drills/frmHSE_Drill_Record_Observation.aspx?A=" + strScramble + "&B=" + clsMiscellaneous.encryptQueryString(tbDrill_Record_Hdr_Id_Hidden.Value);

    }
    protected void btnImprovements_Click(object sender, EventArgs e)
    {

        if (tbDrill_Record_Hdr_Id_Hidden.Value == "")
        { return; }

        // Page.RegisterStartupScript("Change_Color_1", "<script>Change_Color(" + btnEvents.ClientID + ");</script>");

        string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();
        frame1.Attributes["src"] = strAuth_Sign_Photo_URL + "/Quality And Safety/Drills/frmHSE_Drill_Record_Improvement.aspx?A=" + strScramble + "&B=" + clsMiscellaneous.encryptQueryString(tbDrill_Record_Hdr_Id_Hidden.Value);

    }
    protected void btnCorrective_Action_Click(object sender, EventArgs e)
    {
        if (tbDrill_Record_Hdr_Id_Hidden.Value == "")
        { return; }

        //Page.RegisterStartupScript("Change_Color_1", "<script>Change_Color(" + btnEvents.ClientID + ");</script>");

        string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();
        frame1.Attributes["src"] = strAuth_Sign_Photo_URL + "/Quality And Safety/Drills/frmHSE_Drill_Record_Corrective_Action.aspx?A=" + strScramble + "&B=" + clsMiscellaneous.encryptQueryString(tbDrill_Record_Hdr_Id_Hidden.Value);

    }
    protected void btnImage_Click(object sender, EventArgs e)
    {
        if (tbDrill_Record_Hdr_Id_Hidden.Value == "")
        { return; }

        //Page.RegisterStartupScript("Change_Color_1", "<script>Change_Color(" + btnEvents.ClientID + ");</script>");

        string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();
        frame1.Attributes["src"] = strAuth_Sign_Photo_URL + "/Quality And Safety/Drills/frmHSE_Drill_Record_Photo_Upload.aspx?A=" + strScramble + "&B=" + clsMiscellaneous.encryptQueryString(tbDrill_Record_Hdr_Id_Hidden.Value);

    }



    /// <summary>
    /// ///////////////////////////////////
    /// </summary>
    /// <param name="sender"></param>
    /// <param name="e"></param>
    protected void btnPrint_Click(object sender, EventArgs e)
    {


          #region Local Variables
        Conn = new SqlConnection(strConString);
       
        #endregion

        #region To Print the data Crystal Report


        string ErrorString = "";

        string[] strarrParams = new string[1];
        strarrParams[0] = clsSystem_Generic_Info.Report_Dt_Caption;
        //strarrParams[1] = tbRig_Name.Text;
        //strarrParams[2] = "Onboard Crew List For The Period " ;
        
        /// Array for parameter values.
        try
        {
            #region Display Report in Pdf format
            string strAuth_Sign_Photo_URL = ConfigurationManager.ConnectionStrings["SystemURL"].ToString();

            string strReport_File_Path = Server.MapPath("~/Reports/Quality And Safety/Drills/HSE_Drill_Record_Hdr.rpt");
            //string strReport_File_Path = Server.MapPath("~/Reports/Quality And Safety/Drills/HSE_Drill_Record_Hdr_1.rpt");

            

            

            string strTemp_File_Path = Server.MapPath("~/TempReports");
            string PFile = "HSE_Drill_Record_Hdr" + Session.SessionID.ToString() + DateTime.Now.ToString("mm") + DateTime.Now.ToString("ss") + ".pdf";
            string strTemp_File_Name = PFile;
            string strFile_Path = strTemp_File_Path + "\\" + strTemp_File_Name;

            #region These 2 dates are imporatant to decide which header footer to dispay New / Old company

            clsrHSE_Drill_Record_Hdr _Obj = new clsrHSE_Drill_Record_Hdr();

            _Obj.Effective_Date = tbDrill_Dt.Text;
            _Obj.Prj_Cutoff_Date = ConfigurationManager.ConnectionStrings["Prj_Cutoff_Date"].ToString();
            _Obj.Rig_Id = Convert.ToInt16(tbRig_Id_Hidden.Value);
            _Obj.Drill_Record_Hdr_Id = Convert.ToInt16(tbDrill_Record_Hdr_Id_Hidden.Value);
            #endregion


            //   Assign the Fs_Category_Id as 0;;
          
            byte bytReturn=  _Obj.Get_HSE_Drill_Details(ref Conn, strReport_File_Path, PFile, strTemp_File_Path, strarrParams, strAuth_Sign_Photo_URL, 0,ConfigurationManager.ConnectionStrings["SystemURL"].ToString());




            //_Effective_Date = tbDrill_Dt.Text;
            //_Prj_Cutoff_Date = ConfigurationManager.ConnectionStrings["Prj_Cutoff_Date"].ToString();
            //_Rig_Id = Convert.ToInt16(tbRig_Id_Hidden.Value);
            //_Drill_Record_Hdr_Id = Convert.ToInt16(tbDrill_Record_Hdr_Id_Hidden.Value);


            //byte bytReturn = Get_HSE_Drill_Details(ref Conn, strReport_File_Path, PFile, strTemp_File_Path, strarrParams, strAuth_Sign_Photo_URL, 0, ConfigurationManager.ConnectionStrings["SystemURL"].ToString());

            if (bytReturn == 1)
            {
                HttpContext.Current.Response.Clear();
                HttpContext.Current.Response.ClearHeaders();

                HttpContext.Current.Response.ContentType = "application/pdf";

                HttpContext.Current.Response.AppendHeader("Content-Disposition", "attachment; filename=" + strTemp_File_Name + " ");
                HttpContext.Current.Response.TransmitFile(strFile_Path);
                HttpContext.Current.Response.Flush();
                HttpContext.Current.Response.End();
            }

            else
            {
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", "alert('No Data for this criterion')", true);
            }
            #endregion
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }


        #endregion
    }


   


   


}